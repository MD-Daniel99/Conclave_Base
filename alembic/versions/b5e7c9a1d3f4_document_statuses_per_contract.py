"""document statuses per contract

Revision ID: b5e7c9a1d3f4
Revises: c8d1e2f3a4b5
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b5e7c9a1d3f4"
down_revision: Union[str, Sequence[str], None] = "c8d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CONTRACT_TYPES = "'llc_contract','dmk_contract','sdv_contract'"


def upgrade() -> None:
    op.add_column(
        "DOCUMENT",
        sa.Column("contract_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "DOCUMENT",
        sa.Column("act_status", sa.String(length=32), nullable=True),
    )

    op.create_check_constraint(
        "ck_document_contract_status_allowed",
        "DOCUMENT",
        "contract_status IS NULL OR contract_status IN ('Подписан', 'Сделан', 'Отправлен')",
    )
    op.create_check_constraint(
        "ck_document_act_status_allowed",
        "DOCUMENT",
        "act_status IS NULL OR act_status IN ('Подписан', 'Сделан', 'Отправлен')",
    )

    # Preserve legacy patient-level statuses on every contract that already exists.
    op.execute(
        sa.text(
            f'''UPDATE "DOCUMENT" d
                SET contract_status = c.contract_status,
                    act_status = c.act_status
                FROM "CLIENT" c
                WHERE d.client_id = c.client_id
                  AND d.document_type IN ({CONTRACT_TYPES})'''
        )
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_document_act_status_allowed",
        "DOCUMENT",
        type_="check",
    )
    op.drop_constraint(
        "ck_document_contract_status_allowed",
        "DOCUMENT",
        type_="check",
    )
    op.drop_column("DOCUMENT", "act_status")
    op.drop_column("DOCUMENT", "contract_status")
