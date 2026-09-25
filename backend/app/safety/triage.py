"""
Silent triage -- reads every turn against the Clinical Markers table (always in the prompt, see
app.safety.clinical_markers) to produce a coarse read of "which kind of thing is happening", per
documnets/understanding/08_SAFETY_INTERLOCK_AND_TRIAGE.md §1-2 and
documnets/understanding/04_CONVERSATION_PIPELINE.md.

This module ALWAYS runs, on every turn, cache hit or not -- see pipeline step 6 in
documnets/understanding/04_CONVERSATION_PIPELINE.md §1. It is independent of, and runs alongside
(not instead of), app.safety.interlock -- triage informs which self-care pattern is closest;
interlock decides whether to escalate regardless of triage's output.

Per documnets/understanding/09_LATENCY_AND_PERFORMANCE.md §4: triage must stay lightweight signal
extraction, not a heavy model inference step. If this becomes a latency bottleneck, that's a sign
it's been implemented as something heavier than it needs to be -- don't reach for a full LLM call
here; the embedding-based signal pre-filter (app.pipeline.signal_prefilter) is the intended
mechanism, not a second generation call.
"""

from dataclasses import dataclass, field


@dataclass
class TriageReading:
    """One turn's silent-triage output, merged into the session's running conversation state
    (app.pipeline.state) by the caller -- this function itself is stateless."""

    matched_signal_ids: list[str] = field(default_factory=list)
    matched_marker_categories: list[str] = field(default_factory=list)  # e.g. "Safety", "Thought Content"
    candidate_pattern_id: int | None = None


async def read_turn(text: str, *, embedding_provider, db) -> TriageReading:
    """
    Step A of documnets/understanding/04_CONVERSATION_PIPELINE.md: embedding-based signal
    pre-filter against kb_signals.phrasing_embedding (and, where resolvable, kb_symptoms).

    TODO: implement the actual nearest-neighbor query against KBSignal.phrasing_embedding (same
    pgvector cosine_distance pattern as app.safety.interlock.check_interlock), apply
    RETRIEVAL_CONFIDENCE_THRESHOLD, and map results to kb_sufficiency_patterns via
    KBSignal.matched_rules / the enrichment output (app.ingestion.enrichment). Left unimplemented
    here to avoid duplicating the interlock's query logic before a shared helper is extracted --
    see the TODO in app.safety.interlock.check_interlock about surfacing match distance.
    """
    return TriageReading()
