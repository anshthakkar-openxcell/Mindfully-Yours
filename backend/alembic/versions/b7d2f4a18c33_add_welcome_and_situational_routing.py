"""add kb_welcome_responses, kb_situational_routing, therapist_turns.is_preferred

Revision ID: b7d2f4a18c33
Revises: a3c1e7d09b52
Create Date: 2026-10-09

Hand-written (matches the models in app/db/models/kb_convo_content.py). Client drop #2:
AI WELCOME RESPONSES.docx, Situational Routing.xlsx, Best Conversations- Final.docx.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from app.core.config import get_settings

revision: str = "b7d2f4a18c33"
down_revision: Union[str, None] = "a3c1e7d09b52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "kb_therapist_turns",
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "kb_welcome_responses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_file", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False, server_default="en"),
        sa.UniqueConstraint("text", name="uq_kb_welcome_responses_text"),
    )
    op.create_table(
        "kb_situational_routing",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("situation_id", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("situation", sa.Text(), nullable=False),
        sa.Column("tier1_outcome", sa.Text(), nullable=True),
        sa.Column("tier2_outcome", sa.Text(), nullable=True),
        sa.Column("tier3_outcome", sa.Text(), nullable=True),
        sa.Column("self_care_strategy", sa.Text(), nullable=True),
        sa.Column("situation_embedding", Vector(get_settings().embed_dim), nullable=True),
        sa.Column("source_file", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False, server_default="en"),
        sa.UniqueConstraint("situation_id", name="uq_kb_situational_routing_situation_id"),
    )


def downgrade() -> None:
    op.drop_table("kb_situational_routing")
    op.drop_table("kb_welcome_responses")
    op.drop_column("kb_therapist_turns", "is_preferred")
