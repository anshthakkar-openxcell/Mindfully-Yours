"""allow II-III transition layer value

Revision ID: bd49da587f43
Revises: 55d2a5a1ec24
Create Date: 2026-09-28 15:38:17.627829

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bd49da587f43'
down_revision: Union[str, None] = '55d2a5a1ec24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Autogenerate doesn't detect CHECK constraint changes -- written by hand. Widens the allowed
    # `layer` values to include 'II-III', the real, intentional tag for rows parsed from
    # `Layer 2 to 3 Transitions.docx` (confirmed by running ingestion against the live file; not a
    # typo to reject).
    op.drop_constraint("layer_valid", "kb_layer_content", type_="check")
    op.create_check_constraint(
        "layer_valid", "kb_layer_content", "layer IN ('I','II','III','IV','II-III')"
    )


def downgrade() -> None:
    op.drop_constraint("layer_valid", "kb_layer_content", type_="check")
    op.create_check_constraint("layer_valid", "kb_layer_content", "layer IN ('I','II','III','IV')")
