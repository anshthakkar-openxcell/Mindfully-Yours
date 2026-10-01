"""
Retrieval -- implements the three DISTINCT mechanisms from
documnets/understanding/04_CONVERSATION_PIPELINE.md §3. Do not collapse these into one generic
"vector search" function -- treating deterministic lookups as fuzzy search is both slower and less
accurate than what this module does.

1. fetch_probing_guidance   -- direct ID-linked fetch (not a search)
2. search_self_care_content -- genuine semantic RAG search (Tier 1 recommendation, Step F)

Deterministic rule lookup (mechanism 1 in the design doc) lives in app.safety.routing, not here,
since it's safety/tier logic rather than content retrieval.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.kb import KBContentChunk, KBSufficiencyPattern
from app.providers.base import EmbeddingProvider


async def fetch_probing_guidance(pattern_id: int, *, db: AsyncSession) -> str | None:
    """
    Direct ID-linked fetch: once app.safety.routing has identified the closest-matching pattern,
    its `when_to_keep_probing` guidance is fetched by ID -- never searched for. See
    documnets/understanding/04_CONVERSATION_PIPELINE.md Step D/E and
    documnets/understanding/05_KNOWLEDGE_BASE_DEEP_DIVE.md §6.
    """
    pattern = await db.get(KBSufficiencyPattern, pattern_id)
    if pattern is None or pattern.is_placeholder:
        # is_placeholder covers the two known 'check----------' rows -- never surface a
        # placeholder as if it were real guidance. See
        # documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #6.
        return None
    return pattern.probing_guidance


async def search_self_care_content(
    query_text: str,
    *,
    tier: int,
    language: str,
    db: AsyncSession,
    embedding_provider: EmbeddingProvider,
    top_k: int | None = None,  # None -> RETRIEVAL_TOP_K from .env; pass explicitly to override
    query_embedding: list[float] | None = None,  # pass the turn's shared embedding -- see below
) -> list[KBContentChunk]:
    """
    Genuine semantic RAG search -- the ONE place it's actually used, per
    documnets/understanding/04_CONVERSATION_PIPELINE.md Step F (Tier 1 only).

    NOTE: documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #3 -- Phase III/IV content
    (psycho_education, self_care_tool chunks) has not been received from the client yet, so
    kb_content_chunks will be empty in any real environment today. This function is correct to
    call now (it will just return []); do not special-case "no content yet" here -- handle an
    empty result in the caller (app.pipeline.orchestrator) the same way any low-confidence
    retrieval is handled: route to a safe, generic, pre-approved fallback, never a best-effort
    guess (documnets/understanding/06_SIGNAL_ENRICHMENT_PIPELINE.md / CLAUDE.md §6).

    Below-threshold matches are dropped here, not returned -- per CLAUDE.md §6, "below-threshold
    matches should route to a safe, generic, pre-approved fallback -- never let a low-confidence
    match get treated as grounded fact." An empty return therefore means "nothing confident
    enough", which the caller must treat the same as "nothing exists yet".

    `query_embedding`: pass the turn's already-computed embedding (see app.safety.interlock's
    identical parameter) to avoid a redundant ~300-400ms re-embed of the same text.
    """
    settings = get_settings()
    if query_embedding is None:
        [query_embedding] = await embedding_provider.embed([query_text])
    max_distance = 1 - settings.retrieval_confidence_threshold
    resolved_top_k = top_k if top_k is not None else settings.retrieval_top_k

    distance_expr = KBContentChunk.embedding.cosine_distance(query_embedding)
    stmt = (
        select(KBContentChunk, distance_expr.label("distance"))
        .where(
            KBContentChunk.tier == tier,
            KBContentChunk.language == language,
            KBContentChunk.content_type.in_(["psycho_education", "self_care_tool"]),
        )
        .order_by(distance_expr)
        .limit(resolved_top_k)
    )
    result = await db.execute(stmt)
    return [chunk for chunk, distance in result.all() if distance <= max_distance]
