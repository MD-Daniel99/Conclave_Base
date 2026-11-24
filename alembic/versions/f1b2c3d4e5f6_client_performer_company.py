"""add performer company to clients

Revision ID: f1b2c3d4e5f6
Revises: e7a9c3d5f102
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "f1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "e7a9c3d5f102"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "CLIENT",
        sa.Column("performer_company", sa.String(length=128), nullable=True),
    )
    op.create_check_constraint(
        "ck_client_performer_company_allowed",
        "CLIENT",
        "performer_company IS NULL OR performer_company IN ('ООО «ПрОП ДВИЖЕНИЕ ЗЕТ»', 'ООО \"Смарт Движение\"')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_client_performer_company_allowed", "CLIENT", type_="check")
    op.drop_column("CLIENT", "performer_company")
