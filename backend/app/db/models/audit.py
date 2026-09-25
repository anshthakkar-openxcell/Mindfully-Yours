"""
Per-turn audit log -- the AI service's clinical/safety audit trail, required by
documnets/understanding/12_SECURITY_COMPLIANCE_DPDP.md §4 (>=3 year retention, sufficient to
review/audit model operation and outputs on request) and documnets/understanding/04_CONVERSATION_PIPELINE.md
step 13. Writes here MUST be async / never block the response path -- see
documnets/understanding/09_LATENCY_AND_PERFORMANCE.md §8 and app/workers/audit_writer.py.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TurnAuditLog(Base):
    __tablename__ = "turn_audit_log"

    turn_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("sessions.session_id"), nullable=True
    )
    user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    turn_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    served_from: Mapped[str | None] = mapped_column(String, nullable=True)
    # 'exact_cache' | 'semantic_cache' | 'rag_retrieval'
    retrieved_chunk_ids: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    matched_signal_ids: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    matched_rule_id: Mapped[str | None] = mapped_column(String, nullable=True)
    triage_tier: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    interlock_triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interlock_flag_id: Mapped[str | None] = mapped_column(String, nullable=True)
    fallback_scenario_id: Mapped[int | None] = mapped_column(
        ForeignKey("kb_fallback_scenarios.scenario_id"), nullable=True
    )
    latency_ms: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # e.g. {"stt": 120, "retrieval": 45, "llm_first_token": 610, ...}
    kb_version_id: Mapped[int | None] = mapped_column(ForeignKey("kb_versions.version_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
