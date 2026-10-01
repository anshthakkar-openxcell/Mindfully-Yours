"""add tier scoring audit columns

Revision ID: f97bfc5c8578
Revises: bd49da587f43
Create Date: 2026-09-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f97bfc5c8578'
down_revision: Union[str, None] = 'bd49da587f43'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Supports app.pipeline.tier_scoring -- see documnets/understanding/28_TIER_SCORING_APPROACH.md.
    # Deliberately separate from the existing `triage_tier` column, which reflects a single turn's
    # routing-rule match; these reflect the whole conversation's accumulated score.
    op.add_column("turn_audit_log", sa.Column("confidence_score", sa.Float(), nullable=True))
    op.add_column("turn_audit_log", sa.Column("score_tier", sa.SmallInteger(), nullable=True))
    op.add_column(
        "turn_audit_log",
        sa.Column("redirect_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("turn_audit_log", "redirect_ready")
    op.drop_column("turn_audit_log", "score_tier")
    op.drop_column("turn_audit_log", "confidence_score")
