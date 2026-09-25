"""
Fallback & Safety Net evaluation -- the THIRD response type, distinct from both "keep probing" and
"enough signal, route now." Per documnets/understanding/08_SAFETY_INTERLOCK_AND_TRIAGE.md §5 and
documnets/understanding/knowledgebase's CHUNKING_EMBEDDING_STRATEGY.md §5: `trigger_condition` here
describes the CONVERSATION'S OWN SHAPE (turn count, response length, confidence score) -- it is
evaluated as CODE against running conversation state, never embedded or semantically searched.

Real structure (confirmed twice -- see documnets/understanding/05_KNOWLEDGE_BASE_DEEP_DIVE.md §7):
four lettered sections (A insufficient-signal, B contradictory-signal, C disengagement,
D special-population) PLUS a separate 84-row, 15-group disorder-specific matrix. This module
only implements the conversation-shape checks (A/B/C/D) -- the disorder matrix is keyed by
diagnosis, not conversation shape, and is consumed differently (via app.pipeline.retrieval once a
candidate pattern/disorder is already known, not scanned per turn).

CAUTION: the source data (kb_fallback_scenarios) has a real person's name hardcoded into three
escalation_path rows -- see documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #13. Scrub
at ingestion time (app.ingestion.parsers.fallback), don't let it reach any environment beyond local
dev with synthetic data.
"""

from dataclasses import dataclass


@dataclass
class ConversationShapeState:
    """The subset of Redis-backed running conversation state (see app.pipeline.state) relevant to
    fallback evaluation. Kept as its own small dataclass so fallback logic doesn't need to know
    about the full running-state shape."""

    turn_count: int
    consecutive_short_responses: int
    confidence_score: float
    topic_diversity_score: float
    stated_wellbeing_contradicts_content: bool
    seconds_since_last_response: float


@dataclass
class FallbackDecision:
    triggered: bool
    section: str | None = None  # 'A_insufficient' | 'B_contradictory' | 'C_disengagement' | 'D_special_population'
    scenario_type: str | None = None
    bot_script: str | None = None
    escalation_path: str | None = None


def evaluate_fallback(state: ConversationShapeState, *, confidence_threshold: float) -> FallbackDecision:
    """
    Code-evaluated fallback check -- runs AFTER the sufficiency/routing check returns "not enough
    yet" and BEFORE deciding to keep probing, per documnets/understanding/04_CONVERSATION_PIPELINE.md
    Step D's fourth branch.

    TODO: this is a structural skeleton. Real thresholds (e.g. "15+ turns", "8+ turns of one-word
    answers") must be loaded from kb_fallback_scenarios rows (per section), not hardcoded here --
    fetch the matching scenario row's bot_script/escalation_path verbatim once a section/condition
    matches, mirroring app.safety.interlock's verbatim-fetch pattern.
    """
    if state.turn_count >= 15 and state.confidence_score < confidence_threshold:
        return FallbackDecision(triggered=True, section="A_insufficient")

    if state.stated_wellbeing_contradicts_content:
        return FallbackDecision(triggered=True, section="B_contradictory")

    if state.consecutive_short_responses >= 8:
        return FallbackDecision(triggered=True, section="C_disengagement")

    return FallbackDecision(triggered=False)
