"""
Async, non-blocking audit log writes -- pipeline step 13 of
documnets/understanding/04_CONVERSATION_PIPELINE.md. Per
documnets/understanding/09_LATENCY_AND_PERFORMANCE.md §8: audit logging must never block the
response path -- fire it off after (or during) response streaming, not before.

Called via `asyncio.create_task(...)` from app.pipeline.orchestrator, not awaited inline.
"""

from uuid import UUID

from app.core.logging import get_logger
from app.db.models.audit import TurnAuditLog
from app.db.session import AsyncSessionLocal

logger = get_logger(__name__)


async def write_turn_audit_log(
    *,
    session_id: UUID | None,
    user_id: UUID | None,
    turn_number: int | None,
    served_from: str,
    retrieved_chunk_ids: list[str] | None = None,
    matched_signal_ids: list[str] | None = None,
    matched_rule_id: str | None = None,
    triage_tier: int | None = None,
    interlock_triggered: bool = False,
    interlock_flag_id: str | None = None,
    fallback_scenario_id: int | None = None,
    latency_ms: dict | None = None,
    kb_version_id: int | None = None,
) -> None:
    """Opens its own DB session -- this runs detached from the request's session/transaction so a
    slow or failed audit write can never affect the response already streamed to the user."""
    try:
        async with AsyncSessionLocal() as db:
            db.add(
                TurnAuditLog(
                    session_id=session_id,
                    user_id=user_id,
                    turn_number=turn_number,
                    served_from=served_from,
                    retrieved_chunk_ids=retrieved_chunk_ids,
                    matched_signal_ids=matched_signal_ids,
                    matched_rule_id=matched_rule_id,
                    triage_tier=triage_tier,
                    interlock_triggered=interlock_triggered,
                    interlock_flag_id=interlock_flag_id,
                    fallback_scenario_id=fallback_scenario_id,
                    latency_ms=latency_ms,
                    kb_version_id=kb_version_id,
                )
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001 -- a failed audit write must never crash the caller
        logger.error("audit_write_failed", error=str(exc), session_id=str(session_id))
