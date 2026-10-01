"""
Silent triage -- reads every turn against kb_signals/kb_symptoms/kb_sufficiency_patterns to produce
a coarse read of "which kind of thing is happening", per documnets/understanding/08_SAFETY_INTERLOCK_AND_TRIAGE.md
§1-2 and documnets/understanding/04_CONVERSATION_PIPELINE.md.

This module ALWAYS runs, on every turn, cache hit or not -- see pipeline step 6 in
documnets/understanding/04_CONVERSATION_PIPELINE.md §1. It is independent of, and runs alongside
(not instead of), app.safety.interlock -- triage informs which self-care pattern is closest;
interlock decides whether to escalate regardless of triage's output.

Per documnets/understanding/09_LATENCY_AND_PERFORMANCE.md §4: triage must stay lightweight signal
extraction, not a heavy model inference step. `query_embedding` is accepted as an optional
pre-computed vector so the caller (app.pipeline.orchestrator) can embed the turn's text ONCE and
reuse it across interlock + triage + retrieval -- embedding is the expensive network-bound step
(~300-400ms measured live), not the pgvector queries below (single-digit-to-low-double-digit ms
even on kb_signals' 285 rows). Do not have this function call embed() again if a caller already has
the vector; that's exactly the kind of redundant-embedding-per-check pattern that would silently
stack 3-4 network round-trips onto one turn.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.kb import KBSignal, KBSufficiencyPattern, KBSymptom
from app.providers.base import EmbeddingProvider


@dataclass
class TriageReading:
    """One turn's silent-triage output, merged into the session's running conversation state
    (app.pipeline.state) by the caller -- this function itself is stateless."""

    matched_signal_ids: list[str] = field(default_factory=list)
    matched_marker_categories: list[str] = field(default_factory=list)  # e.g. "Safety", "Thought Content"
    candidate_pattern_id: int | None = None


async def read_turn(
    text: str,
    *,
    embedding_provider: EmbeddingProvider,
    db: AsyncSession,
    query_embedding: list[float] | None = None,
) -> TriageReading:
    """
    Step A of documnets/understanding/04_CONVERSATION_PIPELINE.md: embedding-based signal
    pre-filter against kb_signals.phrasing_embedding and kb_symptoms.how_described_embedding, plus
    a candidate-pattern lookup against kb_sufficiency_patterns.pattern_name_embedding (the one
    narrow embedding case on that table).

    HONEST LIMITATION, confirmed by live testing, not a hypothetical risk: kb_signals matching is
    noisy at the individual-signal level -- a completely benign message scored HIGHER similarity to
    a real signal (SIG-228 "Hypomania", 0.488) than a genuine symptom-bearing message scored against
    its own correct match (SIG-261 "Emotional Pain", 0.479). See TRIAGE_SIGNAL_THRESHOLD's comment
    in app.core.config for the full numbers. This is exactly why matched_signal_ids is meant to
    ACCUMULATE across the whole conversation (app.pipeline.state.ConversationState) rather than be
    treated as fact from one turn -- a single noisy match should never be decisive on its own.
    """
    settings = get_settings()
    if query_embedding is None:
        [query_embedding] = await embedding_provider.embed([text])

    matched_signal_ids: list[str] = []

    signal_max_distance = 1 - settings.triage_signal_threshold
    signal_distance = KBSignal.phrasing_embedding.cosine_distance(query_embedding)
    signal_stmt = (
        select(KBSignal.signal_id, signal_distance.label("distance"))
        .where(KBSignal.phrasing_embedding.is_not(None))
        .order_by(signal_distance)
        .limit(settings.triage_top_k)
    )
    for row in (await db.execute(signal_stmt)).all():
        if row.distance <= signal_max_distance:
            matched_signal_ids.append(row.signal_id)

    # kb_symptoms matches contribute BOTH their own symptom_id (the 'EM-xxx' rows -- these are the
    # exact codes kb_routing_rules' Tier 1 trigger_conditions reference, e.g. "EM45 to 54"; see
    # app.ingestion.parsers.common.match_symptom_in_trigger_condition's docstring for how this was
    # confirmed) AND their linked_signal_ids where present. PHYS- rows have no linked_signal_ids
    # (their own symptom_id still gets contributed); EM- rows may or may not, depending on the row.
    symptom_distance = KBSymptom.how_described_embedding.cosine_distance(query_embedding)
    symptom_stmt = (
        select(KBSymptom.symptom_id, KBSymptom.linked_signal_ids, symptom_distance.label("distance"))
        .where(KBSymptom.how_described_embedding.is_not(None))
        .order_by(symptom_distance)
        .limit(settings.triage_top_k)
    )
    for row in (await db.execute(symptom_stmt)).all():
        if row.distance > signal_max_distance:
            continue
        if row.symptom_id not in matched_signal_ids:
            matched_signal_ids.append(row.symptom_id)
        if row.linked_signal_ids:
            for signal_id in row.linked_signal_ids:
                if signal_id not in matched_signal_ids:
                    matched_signal_ids.append(signal_id)

    # Candidate pattern: nearest pattern_name_embedding match, gated by its OWN threshold -- a
    # short-label-to-sentence comparison has a different similarity distribution than phrase-to-
    # phrase signal matching (live-tested cleaner separation: safe messages ~0.30, real matches
    # 0.35-0.49 -- see PATTERN_MATCH_THRESHOLD's comment). is_placeholder excludes the two known
    # 'check----------' rows (documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #6).
    candidate_pattern_id: int | None = None
    pattern_max_distance = 1 - settings.pattern_match_threshold
    pattern_distance = KBSufficiencyPattern.pattern_name_embedding.cosine_distance(query_embedding)
    pattern_stmt = (
        select(KBSufficiencyPattern.pattern_id, pattern_distance.label("distance"))
        .where(
            KBSufficiencyPattern.pattern_name_embedding.is_not(None),
            KBSufficiencyPattern.is_placeholder.is_(False),
        )
        .order_by(pattern_distance)
        .limit(1)
    )
    pattern_row = (await db.execute(pattern_stmt)).first()
    if pattern_row is not None and pattern_row.distance <= pattern_max_distance:
        candidate_pattern_id = pattern_row.pattern_id

    return TriageReading(matched_signal_ids=matched_signal_ids, candidate_pattern_id=candidate_pattern_id)
