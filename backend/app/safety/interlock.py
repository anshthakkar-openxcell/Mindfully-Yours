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
from app.providers.base import EmbeddingProvider

logger = get_logger(__name__)


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


async def check_interlock(
    text: str,
    *,
    db: AsyncSession,
    embedding_provider: EmbeddingProvider,
) -> InterlockResult:
    """
    Check raw user text against the Red Flags table (kb_red_flags). Called on EVERY turn from
    app.pipeline.orchestrator, independent of cache hits, retrieval results, or conversation state.

    The match threshold is deliberately MORE PERMISSIVE than a normal RAG match (see
    REDFLAG_MATCH_THRESHOLD in app.core.config) -- a false positive here costs a moment's extra
    caution; a false negative costs a missed danger signal. Do not reuse
    RETRIEVAL_CONFIDENCE_THRESHOLD for this check.
    """
    settings = get_settings()
    try:
        [query_embedding] = await embedding_provider.embed([text])
    except Exception as exc:  # noqa: BLE001 -- deliberate: ANY failure here must fail safe, not raise past this boundary
        logger.error("interlock_embedding_failed", error=str(exc))
        raise SafetyInterlockError(
            "Embedding call failed during interlock check -- failing toward caution."
        ) from exc

    # Cosine distance: smaller is more similar. pgvector's cosine_distance() is 1 - cosine_similarity,
    # so `distance <= (1 - threshold)` is the "similar enough" condition.
    max_distance = 1 - settings.redflag_match_threshold
    distance_expr = KBRedFlag.trigger_embedding.cosine_distance(query_embedding)
    stmt = (
        select(KBRedFlag, distance_expr.label("distance"))
        .where(KBRedFlag.trigger_embedding.is_not(None))
        .order_by(distance_expr)
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.first()

    if row is None:
        return InterlockResult(triggered=False)

    best_match: KBRedFlag = row[0]
    distance: float = row[1]

    if distance > max_distance:
        # Nearest neighbor exists but isn't close enough -- per REDFLAG_MATCH_THRESHOLD, this
        # threshold is deliberately more permissive than a normal RAG match, but it is still a
        # real threshold, not "always match the nearest row regardless of distance."
        return InterlockResult(triggered=False)

    logger.warning("interlock_triggered", flag_id=best_match.flag_id, distance=distance)

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
