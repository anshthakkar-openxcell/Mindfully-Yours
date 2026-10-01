"""
Running conversation-level tier score -- see documnets/understanding/28_TIER_SCORING_APPROACH.md
for the full design discussion this implements.

Replaces "does this one message qualify for Tier 2/3" with a running 0-100 score that moves a
little with every turn, read off `ConversationState.confidence_score`. The Tier is whichever
bracket the score currently sits in -- a level the conversation has climbed to, not a one-shot
verdict from a single message.

Two separate decisions live here, deliberately kept apart (see 28_TIER_SCORING_APPROACH.md's
"Score and redirect are two different decisions, not one"):
  1. `tier_from_score()` -- how concerning does this look so far. Moves fast, in both directions.
  2. `should_redirect_to_booking()` -- are we actually CONFIDENT enough to push the user toward
     booking a consultation. This is a much bigger action than one more reply, so it requires
     corroboration across turns (multiple distinct signals), not just a score crossing a line.
     A single striking message can spike the score; it should not, by itself, flip this.

This is INDEPENDENT of, and never gates, app.safety.interlock -- a genuine danger phrase escalates
immediately regardless of what this running score says. This module is for the slower, accumulating
picture of "how serious is this pattern turning out to be", not a substitute for instant danger
detection.

ALL numbers in this module (severity points, established-bonus points) are explicitly provisional,
same caveat as every other threshold in this project -- a starting point for live testing and
clinical-team review, not a validated model. See each constant's own comment for what's been
tested so far and what hasn't.
"""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.kb import KBSignal, KBSymptom
from app.pipeline.state import ConversationState
from app.providers.base import LLMProvider

logger = get_logger(__name__)

# Points added per NEWLY observed (never-seen-before-this-conversation) signal, by kb_signals'
# severity (1/2/3) or kb_symptoms.max_linked_severity for EM-/PHYS- ids. NOT live-tested against
# real conversations yet -- illustrative starting point pending clinical-team review, same posture
# as every other provisional number in this project (see REDFLAG_MATCH_THRESHOLD etc.). Chosen so
# that a single mild signal alone can't cross into Tier 2 (40), but two moderate ones or one severe
# one meaningfully can.
SEVERITY_POINTS: dict[int, int] = {1: 8, 2: 15, 3: 25}
# Fallback for signals/symptoms with no severity recorded (e.g. most EM- rows, which are free-text
# category labels with no clinical severity rating -- see kb_symptoms' docstring) -- small and
# deliberately below even the mildest rated signal, since an untriaged mention shouldn't count as
# much as a clinically-weighted one.
UNRATED_SIGNAL_POINTS = 4

# UPGRADED 2026-09-30 (was a keyword-cue list -- see git history / 28_TIER_SCORING_APPROACH.md for
# the original heuristic and why it was replaced). Detecting "has the user told us how long this has
# been going on" and "has the user told us it's affecting their daily life" is now a small, cheap
# LLM read of the CURRENT message, not a keyword search -- see `_detect_duration_and_impact_llm()`
# below. Keyword matching both missed real answers phrased differently and had no sense of context
# (e.g. couldn't tell "I've been better lately" apart from an active complaint). The LLM is asked to
# quote the exact part of the message that justifies a "yes", which keeps this checkable rather than
# an unexplained opinion -- see that function's docstring.
DURATION_IMPACT_PROMPT = """Read ONLY this one message from a user in a mental wellness chat. Do not assume anything beyond what is actually written.

Message: "{text}"

Answer two yes/no questions about this message alone:
1. DURATION: Does the message state how long something has been going on (e.g. "for weeks", "since last month", "a few days now")?
2. IMPACT: Does the message state that something is affecting the user's daily life (e.g. work, sleep, eating, relationships, school)?

Respond in EXACTLY this format and nothing else, two lines:
DURATION: yes or no - the exact quote that justifies it, or "none"
IMPACT: yes or no - the exact quote that justifies it, or "none\""""

_DURATION_RE = re.compile(r"DURATION:\s*(yes|no)", re.IGNORECASE)
_IMPACT_RE = re.compile(r"IMPACT:\s*(yes|no)", re.IGNORECASE)


def _points_for_severity(severity: int | None) -> int:
    if severity is None:
        return UNRATED_SIGNAL_POINTS
    return SEVERITY_POINTS.get(severity, UNRATED_SIGNAL_POINTS)


async def _new_signal_points(new_signal_ids: list[str], *, db: AsyncSession) -> int:
    """Looks up severity for only the genuinely NEW ids this turn contributed (the caller is
    responsible for filtering to ids not already in conv_state.observed_signal_ids -- repeating the
    same worry three different ways must not triple-count, per 28_TIER_SCORING_APPROACH.md)."""
    if not new_signal_ids:
        return 0

    sig_ids = [sid for sid in new_signal_ids if sid.startswith("SIG")]
    symptom_ids = [sid for sid in new_signal_ids if not sid.startswith("SIG")]

    severities: dict[str, int | None] = dict.fromkeys(new_signal_ids, None)

    if sig_ids:
        stmt = select(KBSignal.signal_id, KBSignal.severity).where(KBSignal.signal_id.in_(sig_ids))
        for row in (await db.execute(stmt)).all():
            severities[row.signal_id] = row.severity

    if symptom_ids:
        stmt = select(KBSymptom.symptom_id, KBSymptom.max_linked_severity).where(
            KBSymptom.symptom_id.in_(symptom_ids)
        )
        for row in (await db.execute(stmt)).all():
            severities[row.symptom_id] = row.max_linked_severity

    return sum(_points_for_severity(severities[sid]) for sid in new_signal_ids)


async def _detect_duration_and_impact_llm(text: str, *, llm: LLMProvider) -> tuple[bool, bool]:
    """
    Small, cheap classification call -- NOT the main conversation reply, and not streamed to the
    user. Low temperature + a tight max_tokens budget since this only needs two short lines back.

    Fails CLOSED, not safe-by-default-true: if the call errors, times out, or comes back in a shape
    we can't parse, both flags are treated as "not yet established" for this turn -- the worse
    outcome here is asking the question again next turn, not wrongly marking something confirmed
    that was never actually said. That's the right direction to fail for a flag that only ever GATES
    the redirect-to-booking decision, never blocks or delays anything else.
    """
    prompt = DURATION_IMPACT_PROMPT.format(text=text)
    try:
        chunks: list[str] = []
        async for chunk in llm.generate_stream(prompt, max_tokens=60, temperature=0.0):
            chunks.append(chunk)
        response = "".join(chunks)
    except Exception as exc:  # noqa: BLE001 -- fail closed (see docstring), never crash the turn over this
        logger.error("tier_duration_impact_llm_failed", error=str(exc))
        return False, False

    duration_match = _DURATION_RE.search(response)
    impact_match = _IMPACT_RE.search(response)
    duration = bool(duration_match) and duration_match.group(1).lower() == "yes"
    impact = bool(impact_match) and impact_match.group(1).lower() == "yes"
    if duration_match is None or impact_match is None:
        logger.warning("tier_duration_impact_unparseable", raw_response=response[:200])
    return duration, impact


async def update_score(
    text: str, new_signal_ids: list[str], conv_state: ConversationState, *, db: AsyncSession, llm: LLMProvider
) -> None:
    """
    Mutates `conv_state` in place, same style as `ConversationState.record_turn`. Call this once
    per turn, on EVERY turn (not just cache misses) -- same "always runs" posture as triage, so the
    score reflects the whole conversation, not just the turns that happened to reach the LLM.

    `new_signal_ids` should be the subset of this turn's matched signals not already in
    `conv_state.observed_signal_ids` -- pass the full list and this still works, but points would
    then double-count repeats, defeating the "new concern vs. repeat" rule from the design doc.
    """
    settings = get_settings()

    gained = await _new_signal_points(new_signal_ids, db=db)
    # Cap per-turn gain -- kb_signals matching is confirmed noisy (see TRIAGE_SIGNAL_THRESHOLD's
    # comment): one message can trip many simultaneous signal/symptom matches from the top-K triage
    # lookup, which uncapped would let a single noisy turn jump straight to 100. The score is meant
    # to accumulate gradually ACROSS a conversation, not spike from one message's worth of matches.
    gained = min(gained, settings.tier_score_max_gain_per_turn)

    # Once established, stays established -- these represent facts the user has told us, which
    # don't become un-true later in the conversation. Skip the LLM call entirely once both are
    # already known -- no need to keep asking a question that's already answered.
    newly_established_bonus = 0
    if not (conv_state.duration_established and conv_state.impact_established):
        duration_now, impact_now = await _detect_duration_and_impact_llm(text, llm=llm)
        if duration_now and not conv_state.duration_established:
            conv_state.duration_established = True
            newly_established_bonus += 10
        if impact_now and not conv_state.impact_established:
            conv_state.impact_established = True
            newly_established_bonus += 10

    if gained == 0 and newly_established_bonus == 0:
        # A quiet turn -- no new signal, nothing new established. Let the score ease back down
        # rather than staying stuck at a high point from one earlier message (the "score can go
        # down, not just up" principle from the design doc).
        conv_state.confidence_score = max(0.0, conv_state.confidence_score - settings.tier_score_decay_per_quiet_turn)
    else:
        conv_state.confidence_score = min(100.0, conv_state.confidence_score + gained + newly_established_bonus)

    logger.info(
        "tier_score_updated",
        score=conv_state.confidence_score,
        gained=gained,
        duration_established=conv_state.duration_established,
        impact_established=conv_state.impact_established,
    )


def tier_from_score(score: float) -> int:
    """
    Returns 1 or 2 -- NEVER 3. Tier 3 is exclusively the safety interlock's crisis/SOS path (see
    app.safety.interlock), triggered only by actually critical content, checked independently every
    turn. It must never be reachable by accumulating points from an ordinary conversation, no matter
    how high the running score climbs -- an accumulating work-stress conversation and a genuine
    self-harm disclosure must never be able to share a label. CORRECTED 2026-09-30: this function
    used to map score >= 70 to a third bracket literally called "Tier 3", which is exactly the wrong
    idea -- see documnets/understanding/28_TIER_SCORING_APPROACH.md's "Tier 3 is reserved exclusively
    for genuine crisis" section for the full correction.
    """
    settings = get_settings()
    if score >= settings.tier2_score_min:
        return 2
    return 1


def should_redirect_to_booking(conv_state: ConversationState) -> bool:
    """
    The confidence gate -- see this module's docstring and 28_TIER_SCORING_APPROACH.md's "Score and
    redirect are two different decisions" section. Reaching Tier 2 is NOT sufficient on its own;
    redirecting to booking additionally requires the two key clinical questions to have been
    answered (duration + impact) AND enough genuinely distinct signals to corroborate this isn't
    one dramatic sentence. Tune via REDIRECT_MIN_DISTINCT_SIGNALS.
    """
    settings = get_settings()
    if tier_from_score(conv_state.confidence_score) < 2:
        return False
    if not (conv_state.duration_established and conv_state.impact_established):
        return False
    return len(conv_state.observed_signal_ids) >= settings.redirect_min_distinct_signals
