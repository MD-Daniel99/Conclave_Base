"""Add contract-style expense fields to client accounting.

Revision ID: 5a8c1d2e3f40
Revises: 2f4d9a7c1b30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5a8c1d2e3f40"
down_revision: Union[str, Sequence[str], None] = "2f4d9a7c1b30"
branch_labels = None
depends_on = None


EXPENSE_COLUMNS = (
    "prosthetist_work",
    "patient_travel",
    "patient_accommodation",
    "patient_payment",
    "other_expenses",
    "agency_expenses",
)
LEGACY_EXPENSE_COLUMNS = (
    "prosthetist_salary",
    "agent_salary",
    "support_salary",
)

def upgrade() -> None:
    bind = op.get_bind()
    existing = {
        column["name"]
        for column in sa.inspect(bind).get_columns("CLIENT")
    }

    # Эти колонки всё ещё используются текущим приложением,
    # но в старой цепочке Alembic они создавались не всегда.
    for column_name in LEGACY_EXPENSE_COLUMNS:
        if column_name not in existing:
            op.add_column(
                "CLIENT",
                sa.Column(
                    column_name,
                    sa.Float(),
                    nullable=False,
                    server_default=sa.text("0"),
                ),
            )

    for column_name in EXPENSE_COLUMNS:
        if column_name not in existing:
            op.add_column(
                "CLIENT",
                sa.Column(
                    column_name,
                    sa.Float(),
                    nullable=False,
                    server_default=sa.text("0"),
                ),
            )

    bind.execute(sa.text("""
        UPDATE "CLIENT"
        SET prosthetist_work = COALESCE(prosthetist_salary, 0),
            agency_expenses = COALESCE(agent_salary, 0),
            other_expenses = COALESCE(support_salary, 0)
        WHERE prosthetist_work = 0
          AND agency_expenses = 0
          AND other_expenses = 0
    """))


def downgrade() -> None:
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("CLIENT")}
    for column_name in reversed(EXPENSE_COLUMNS):
        if column_name in existing:
            op.drop_column("CLIENT", column_name)

