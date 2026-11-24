"""Add accounting expense history and user presence timestamps.

Revision ID: f3a9c2d1e8b4
Revises: e2f7a1c9d4b0
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f3a9c2d1e8b4"
down_revision: Union[str, Sequence[str], None] = "e2f7a1c9d4b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("CLIENT", sa.Column("accounting_expenses", sa.JSON(), nullable=True))
    op.add_column("CLIENT", sa.Column("accounting_expense_status", sa.JSON(), nullable=True))
    op.add_column("USERS", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("USERS", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("USERS", "last_seen_at")
    op.drop_column("USERS", "last_login_at")
    op.drop_column("CLIENT", "accounting_expense_status")
    op.drop_column("CLIENT", "accounting_expenses")
