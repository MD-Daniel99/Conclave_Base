"""add per-client VAT percent

Revision ID: c9f0a1b2c3d4
Revises: f1b2c3d4e5f6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c9f0a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = "f1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The field may already exist if the earlier manual recovery SQL was run.
    # Keep this upgrade safe to apply in either case without touching client rows.
    op.execute(
        sa.text(
            'ALTER TABLE "CLIENT" ADD COLUMN IF NOT EXISTS '
            'vat_percent DOUBLE PRECISION NOT NULL DEFAULT 20'
        )
    )


def downgrade() -> None:
    op.drop_column("CLIENT", "vat_percent")
