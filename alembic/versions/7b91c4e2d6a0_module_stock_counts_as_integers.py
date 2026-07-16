"""Store module movement counters as non-negative integers.

Revision ID: 7b91c4e2d6a0
Revises: 5a8c1d2e3f40
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7b91c4e2d6a0"
down_revision: Union[str, Sequence[str], None] = "5a8c1d2e3f40"
branch_labels = None
depends_on = None


COUNT_COLUMNS = ("ordered", "recd", "pending", "prosthetist_keep")


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"]: column for column in sa.inspect(bind).get_columns("MODULES")}

    for name in COUNT_COLUMNS:
        if name not in columns:
            continue
        # Старые поля были строковыми и могли содержать артикулы/комментарии.
        # Числом признаём только самостоятельное неотрицательное целое значение.
        op.execute(sa.text(
            f'UPDATE "MODULES" SET "{name}" = CASE '
            f'WHEN btrim(COALESCE("{name}"::text, \'\')) ~ \'^[0-9]+$\' '
            f'THEN btrim("{name}"::text) ELSE \'0\' END'
        ))
        op.alter_column(
            "MODULES",
            name,
            existing_type=columns[name]["type"],
            type_=sa.Integer(),
            nullable=False,
            server_default="0",
            postgresql_using=f'"{name}"::integer',
        )


def downgrade() -> None:
    for name in COUNT_COLUMNS:
        op.alter_column(
            "MODULES",
            name,
            existing_type=sa.Integer(),
            type_=sa.String(length=64),
            nullable=name == "prosthetist_keep",
            server_default=None,
            postgresql_using=f'"{name}"::text',
        )
