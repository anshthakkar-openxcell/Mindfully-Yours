"""add kb_translations (pre-translated fixed replies for Hindi / Hinglish users)

Revision ID: c9e5a1b2d744
Revises: b7d2f4a18c33
Create Date: 2026-10-09
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9e5a1b2d744"
down_revision: Union[str, None] = "b7d2f4a18c33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kb_translations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_hash", sa.String(), nullable=False),
        sa.Column("style", sa.String(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("translated_text", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint("style IN ('hi','hinglish')", name="translation_style_valid"),
        sa.UniqueConstraint("source_hash", "style", name="uq_kb_translations_hash_style"),
    )


def downgrade() -> None:
    op.drop_table("kb_translations")
