"""
The safety interlock. THE most important module in this codebase.

Per documnets/understanding/01_PROJECT_OVERVIEW.md principle #2 and 08_SAFETY_INTERLOCK_AND_TRIAGE.md:
- Runs on EVERY turn, unconditionally -- including cache hits, retries, and error paths.
- Is deterministic-adjacent: phrase MATCHING is embedding-based (to catch disguised/indirect
  language), but the RESPONSE is always a fetched verbatim script, never LLM-generated.
- Fails SAFE, upward -- on timeout, low confidence, or a provider outage, default to the more
  cautious path, never the more permissive one. See `check_interlock`'s except block below.
- Can force escalation regardless of anything else in the pipeline. Nothing overrides this module;
  this module is not gated by anything upstream of it.

Do not "optimize" this by trimming the trigger-phrase set or lowering match thoroughness for
latency -- per documnets/understanding/09_LATENCY_AND_PERFORMANCE.md §4, if this is slow, the fix
is better indexing, not a shorter rule list.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import MissingBotScriptError, SafetyInterlockError
from app.core.logging import get_logger
from app.db.models.kb import KBRedFlag
from app.db.models.kb_convo_content import KBClarificationPhrase
from app.providers.base import EmbeddingProvider

logger = get_logger(__name__)

# Flags where a MEDIUM-confidence match (between REDFLAG_MATCH_THRESHOLD and
# REDFLAG_SOFT_ZONE_THRESHOLD) gets a gentle, real clarifying question instead of an immediate hard
# escalation. Deliberately a small, explicit allowlist added only after confirming with real data
# that THIS flag produces false positives on ordinary language -- see
# documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #28: "I want to leave my partner" (zero
# danger content) scored 0.46-0.59 against RF-028, because every one of its example phrases mentions
# "partner" and the embedding model clusters on that shared vocabulary, not real danger content.
#
# Suicide/self-harm flags (RF-018, RF-019, RF-025, ...) are deliberately NEVER added here, no matter
# how noisy their matching turns out to be -- for those, a missed or delayed response is the one
# failure mode this project will never accept, so they keep the original single-threshold hard
# escalation unconditionally. Add a flag here only with the same kind of concrete, live-tested
# false-positive evidence RF-028 has -- never as a blanket policy.
SOFT_ZONE_ELIGIBLE_FLAGS = {"RF-028"}

# Suicide-ideation flags -- explicitly excluded from SOFT_ZONE_ELIGIBLE_FLAGS above; a match on these
# always hard-escalates, never gets a softer clarifying path.
# CONFIRMED, LIVE-TESTED GAP (2026-09-29, see documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md
# #28's follow-up): canonical, explicit disclosures -- "i want to kill myself" (0.39), "i want to end
# my life" (0.39), "i've been thinking about suicide" (0.39) -- ALL scored BELOW the standard
# REDFLAG_MATCH_THRESHOLD (0.44) and were silently missed. Two compounding problems, both fixed below:
#   1. The threshold itself is too high for how these flags' trigger phrases sit in embedding space.
#   2. The old code only ever looked at the SINGLE globally-nearest red flag across all 31 rows --
#      for "i've been thinking about suicide", the nearest flag overall was RF-020 (Psychotic
#      Feature) at 0.39, with RF-019/RF-018 sitting right behind it at effectively the same
#      similarity but never even considered, because they weren't literally in first place.
# Fixed by checking these flags specifically among the top candidates (not just the single best),
# against a lower, more sensitive threshold (REDFLAG_CRITICAL_THRESHOLD, 0.36).
#
# RF-025 ("suicidal/self-mutilating behaviours") was tried here too but REMOVED after live testing
# (2026-09-29) found its trigger_embedding is contaminated by its own source phrasing -- one of its 5
# trigger_phrases is "banging my head/cutting my wrist/slamming my fist in the wall", and "slamming my
# fist in the wall" shares enough surface vocabulary with ordinary anger-at-someone-else language that
# RF-025 matched "i feel like hitting him" at 0.39, "i had a fight with my best friend" at 0.41, and
# "i got so angry i wanted to punch a wall" at 0.48 -- all with ZERO self-harm content -- while a real
# disclosure like "i've been cutting myself lately" scored only 0.47. There is no threshold that
# separates those two bands for RF-025 (the false positives score HIGHER than that real disclosure).
# RF-025 doesn't need this list anyway: genuine self-harm disclosures already clear the ordinary
# REDFLAG_MATCH_THRESHOLD (0.44) via the normal top-1 path (0.47-0.64 in testing), and the one
# indirect-phrasing case that motivated adding RF-025 here ("sometimes i think about ending it all")
# is independently caught by RF-018 alone (0.39). Do not re-add RF-025 here without first fixing its
# underlying trigger_phrases in the source data.
#
# This intentionally trades toward MORE false positives on RF-018/RF-019 specifically, though testing
# found them far cleaner than RF-025 (ordinary messages like "i had a fight with my mom" score only
# 0.19-0.29 against RF-018/RF-019, comfortably below 0.36). That tradeoff is deliberate, not an
# oversight: per this module's own stated principle, a missed disclosure is the one failure mode this
# project will never accept, while an occasional unnecessary "are you safe right now" check-in is a
# mild, acceptable cost. Unlike RF-028's soft zone, there is no gentler path here -- a match still
# gets the full, unconditional hard escalation (verbatim bot script), exactly as any other interlock
# trigger.
CRITICAL_SELF_HARM_FLAGS = {"RF-018", "RF-019"}

# Flags whose OWN trigger_phrases are confirmed too broad for the generic REDFLAG_MATCH_THRESHOLD --
# they need a stricter, flag-specific bar rather than the standard one.
# RF-025 CONFIRMED, LIVE-TESTED (2026-09-29): one of its 5 source trigger_phrases is "banging my
# head/cutting my wrist/slamming my fist in the wall". "slamming my fist in the wall" pulls RF-025's
# embedding toward generic "fist/hitting/physical" vocabulary, so it matches ordinary anger directed
# at OTHER people -- zero self-harm content -- via the plain top-1 check, ABOVE the standard 0.44 bar:
# "i feel like hitting him" 0.39 (below 0.44, safe), "i had a fight with my best friend and i feel
# like hitting him" 0.48 (ABOVE 0.44, falsely hard-escalated as RF-025 "suicidal/self-mutilating").
# Notably RF-001 ("aggressive behaviour", the semantically correct flag for anger-at-others) does NOT
# fire on these same phrases either (0.36-0.41, below its own 0.44 bar) -- confirming these messages
# genuinely aren't red-flag material at all; RF-025 is uniquely over-broad here, not the threshold.
# 0.50 was chosen because every tested anger/conflict false positive tops out at 0.48, while most real
# self-harm disclosures scored 0.57-0.64; the one exception, "i've been cutting myself lately" at
# 0.47, would still be missed at this threshold -- an acknowledged residual gap. The real fix is
# correcting RF-025's source trigger_phrases (removing or clarifying "slamming my fist in the wall")
# with the clinical team, not further threshold tuning -- this is a stopgap, not a solved problem.
NOISY_FLAG_THRESHOLDS: dict[str, float] = {"RF-025": 0.50}


@dataclass
class InterlockResult:
    triggered: bool
    flag_id: str | None = None
    clinical_meaning: str | None = None
    immediate_action: str | None = None
    bot_script: str | None = None
    escalation_target: str | None = None
    requires_human_alert: bool = False
    # True when a flag matched but has no bot_script (RF-028-031 today) -- see
    # documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #1. The caller MUST treat this as
    # a hard alert-to-human path, never fall back to LLM generation.
    possible_concern: bool = False
    # True for a medium-confidence match on a SOFT_ZONE_ELIGIBLE_FLAGS flag -- `triggered` stays
    # False (no hard escalation, no verbatim script), but `clarifying_guidance` carries a real,
    # doctor-written follow-up question the caller should weave into the normal LLM response,
    # instead of either silently ignoring the possible concern or over-escalating a likely-benign
    # message.
    clarifying_guidance: str | None = None


async def check_interlock(
    text: str,
    *,
    db: AsyncSession,
    embedding_provider: EmbeddingProvider,
    query_embedding: list[float] | None = None,
) -> InterlockResult:
    """
    Check raw user text against the Red Flags table (kb_red_flags). Called on EVERY turn from
    app.pipeline.orchestrator, independent of cache hits, retrieval results, or conversation state.

    The match threshold is deliberately MORE PERMISSIVE than a normal RAG match (see
    REDFLAG_MATCH_THRESHOLD in app.core.config) -- a false positive here costs a moment's extra
    caution; a false negative costs a missed danger signal. Do not reuse
    RETRIEVAL_CONFIDENCE_THRESHOLD for this check.

    `query_embedding`: pass the turn's already-computed embedding (the orchestrator embeds once per
    turn and reuses it across interlock + triage + retrieval) to avoid a second ~300-400ms network
    round-trip for the identical text. Only embeds here if the caller genuinely doesn't have one yet
    (e.g. a standalone/test call).
    """
    settings = get_settings()
    if query_embedding is None:
        try:
            [query_embedding] = await embedding_provider.embed([text])
        except Exception as exc:  # noqa: BLE001 -- deliberate: ANY failure here must fail safe, not raise past this boundary
            logger.error("interlock_embedding_failed", error=str(exc))
            raise SafetyInterlockError(
                "Embedding call failed during interlock check -- failing toward caution."
            ) from exc

    # Cosine distance: smaller is more similar. pgvector's cosine_distance() is 1 - cosine_similarity,
    # so `distance <= (1 - threshold)` is the "similar enough" condition.
    distance_expr = KBRedFlag.trigger_embedding.cosine_distance(query_embedding)
    # Top-K, not top-1 -- see CRITICAL_SELF_HARM_FLAGS's docstring: a suicide/self-harm flag can sit
    # just behind an unrelated flag in similarity and still need to be caught. 15 is comfortably above
    # kb_red_flags' full row count (31 total, cheap either way) so this never misses a critical flag
    # that's merely not in first place.
    stmt = (
        select(KBRedFlag, distance_expr.label("distance"))
        .where(KBRedFlag.trigger_embedding.is_not(None))
        .order_by(distance_expr)
        .limit(15)
    )
    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return InterlockResult(triggered=False)

    # Never-miss check FIRST, ahead of the general top-1 logic below: scan every candidate (not just
    # the single nearest) for a suicide/self-harm flag clearing the lower, more sensitive
    # REDFLAG_CRITICAL_THRESHOLD. See CRITICAL_SELF_HARM_FLAGS's docstring for why this exists and
    # why it deliberately accepts more false positives in exchange for never missing a real one.
    max_distance_critical = 1 - settings.redflag_critical_threshold
    critical_candidates = [r for r in rows if r[0].flag_id in CRITICAL_SELF_HARM_FLAGS and r[1] <= max_distance_critical]
    if critical_candidates:
        best_critical = min(critical_candidates, key=lambda r: r[1])
        best_match: KBRedFlag = best_critical[0]
        distance: float = best_critical[1]
        logger.warning("interlock_triggered_critical_topk", flag_id=best_match.flag_id, distance=distance)
        return _hard_escalate(best_match)

    best_match = rows[0][0]
    distance = rows[0][1]

    # A flag in NOISY_FLAG_THRESHOLDS needs a stricter bar than the generic one -- see that
    # constant's docstring. Every other flag is unaffected.
    required_similarity = NOISY_FLAG_THRESHOLDS.get(best_match.flag_id, settings.redflag_match_threshold)
    if distance > (1 - required_similarity):
        # Nearest neighbor exists but isn't close enough -- per REDFLAG_MATCH_THRESHOLD, this
        # threshold is deliberately more permissive than a normal RAG match, but it is still a
        # real threshold, not "always match the nearest row regardless of distance."
        return InterlockResult(triggered=False)

    # SOFT ZONE: for the small, explicit set of flags confirmed prone to false positives (see
    # SOFT_ZONE_ELIGIBLE_FLAGS's docstring), a medium-confidence match does NOT hard-escalate --
    # it surfaces a real clarifying question instead. Every other flag keeps the original,
    # unconditional single-threshold hard-escalation behavior, unchanged.
    if best_match.flag_id in SOFT_ZONE_ELIGIBLE_FLAGS:
        max_distance_high = 1 - settings.redflag_soft_zone_threshold
        if distance > max_distance_high:
            logger.info("interlock_soft_zone_concern", flag_id=best_match.flag_id, distance=distance)
            clarifying = await _fetch_clarifying_phrase(query_embedding, db=db)
            return InterlockResult(
                triggered=False,
                flag_id=best_match.flag_id,
                clinical_meaning=best_match.clinical_meaning,
                possible_concern=True,
                clarifying_guidance=clarifying,
            )

    logger.warning("interlock_triggered", flag_id=best_match.flag_id, distance=distance)
    return _hard_escalate(best_match)


def _hard_escalate(best_match: KBRedFlag) -> InterlockResult:
    """The unconditional hard-escalation path, shared by the ordinary top-1 match and the
    never-miss CRITICAL_SELF_HARM_FLAGS top-K check above -- identical outcome either way."""
    if best_match.bot_script is None:
        # Per documnets/understanding/08_SAFETY_INTERLOCK_AND_TRIAGE.md §4: NEVER let this fall
        # through to LLM generation. The caller must route straight to a human alert.
        missing_script_error = MissingBotScriptError(best_match.flag_id)
        logger.critical(
            "interlock_missing_bot_script", flag_id=best_match.flag_id, error=str(missing_script_error)
        )
        return InterlockResult(
            triggered=True,
            flag_id=best_match.flag_id,
            clinical_meaning=best_match.clinical_meaning,
            immediate_action=best_match.immediate_action,
            bot_script=None,
            escalation_target=best_match.escalation_target,
            requires_human_alert=True,
        )

    return InterlockResult(
        triggered=True,
        flag_id=best_match.flag_id,
        clinical_meaning=best_match.clinical_meaning,
        immediate_action=best_match.immediate_action,
        bot_script=best_match.bot_script,  # fetched verbatim -- NEVER paraphrase this
        escalation_target=best_match.escalation_target,
        requires_human_alert=False,
    )


async def _fetch_clarifying_phrase(query_embedding: list[float], *, db: AsyncSession) -> str | None:
    """
    Nearest real, doctor-written clarifying question from kb_clarification_phrases (115 rows,
    including a "Clarifying Relationships" category -- a direct fit for RF-028's soft-zone case).
    Reuses the turn's already-computed embedding -- no extra network call. Unfiltered by any
    confidence threshold deliberately: in the soft zone we already know to ask SOMETHING gentle,
    so the nearest real question is used as-is rather than risking an empty result from a second
    threshold stacked on top of the first.
    """
    distance_expr = KBClarificationPhrase.phrase_embedding.cosine_distance(query_embedding)
    stmt = (
        select(KBClarificationPhrase.phrase)
        .where(KBClarificationPhrase.phrase_embedding.is_not(None))
        .order_by(distance_expr)
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.first()
    return row.phrase if row else None
