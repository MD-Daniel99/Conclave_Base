"""add component stock state

Revision ID: e2f7a1c9d4b0
Revises: d1e2f3a4b5c6
Create Date: 2026-08-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2f7a1c9d4b0"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "MODULES",
        sa.Column("is_in_stock", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_MODULES_is_in_stock", "MODULES", ["is_in_stock"], unique=False)

    # Все уже существующие бесхозные комплектующие переносятся на новую вкладку
    # «Склад», чтобы после обновления они исчезли из Рабочего склада.
    op.execute(sa.text('UPDATE "MODULES" SET is_in_stock = true WHERE client_id IS NULL'))


def downgrade() -> None:
    op.drop_index("ix_MODULES_is_in_stock", table_name="MODULES")
    op.drop_column("MODULES", "is_in_stock")
