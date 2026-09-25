"""
The conversation session record.

SCOPE NOTE (see documnets/understanding/11_DATA_MODEL_AND_STORAGE.md §4): this table straddles the
AI-service/backend boundary. The (out-of-scope) NestJS backend likely owns session *creation* and
overall lifecycle; the AI service needs to *read* user_id/language/session_id and *write*
assigned_tier, summary, mood_tag, and lifecycle_state transitions produced by its own routing
decisions. Resolve final ownership with whoever builds the backend -- this model is defined here
so the AI service can migrate/own it if that's how the split lands, without blocking on that
decision today.

Note this is named `conversation_session.py` (not `session.py`) to avoid any confusion with
app/db/session.py (the SQLAlchemy session factory) -- an easy import-path mistake otherwise.

The fast-moving, per-turn conversation state (Step B of documnets/understanding/04_CONVERSATION_PIPELINE.md
-- observed signals, turn count, confidence score) does NOT live here. It lives in Redis, keyed by
session_id, per 11_DATA_MODEL_AND_STORAGE.md §4's Redis schema note -- it must be sub-millisecond
fast on every turn and has no reason to round-trip through Postgres.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ConversationSession(Base):
    """The 4-state session lifecycle (Live -> Closed -> Tiered -> Shared) named explicitly in the
    architecture PDFs' Storage section. NOTE: documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md
    #7 -- whether Tier 3 and "Crisis" are the same routing outcome or two distinct ones is UNRESOLVED
    across the source PDFs. `assigned_tier` below assumes the 3-tier model; if the 4-state model is
    confirmed, add a separate `crisis_flag: bool` column rather than overloading tier=3 to mean both
    "practitioner referral" and "SOS" -- do not conflate the two without re-checking that decision."""

    __tablename__ = "sessions"

    session_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    mode: Mapped[str | None] = mapped_column(String, nullable=True)  # 'voice' | 'text' | 'avatar'
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")
    lifecycle_state: Mapped[str] = mapped_column(String, nullable=False, default="live")
    assigned_tier: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # persisted for next session's context
    mood_tag: Mapped[str | None] = mapped_column(String, nullable=True)
    livekit_room_id: Mapped[str | None] = mapped_column(String, nullable=True)  # voice/avatar only
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("mode IN ('voice','text','avatar') OR mode IS NULL", name="mode_valid"),
        CheckConstraint(
            "lifecycle_state IN ('live','closed','tiered','shared')", name="lifecycle_state_valid"
        ),
        CheckConstraint("assigned_tier IN (1,2,3) OR assigned_tier IS NULL", name="assigned_tier_range"),
    )
