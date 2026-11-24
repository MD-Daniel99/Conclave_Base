"""Independent numbering for Smart and ZET LLC contracts, starting at 030.

Revision ID: 8c30a9e20261110
Revises: 7b6e20261109

Existing DOCUMENT records, numbers and client data remain unchanged.
"""
from alembic import op
import sqlalchemy as sa

revision = "8c30a9e20261110"
down_revision = "7b6e20261109"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "CONTRACT_NUMBER_COUNTER",
        sa.Column("template_key", sa.String(32), primary_key=True),
        sa.Column("next_number", sa.Integer(), nullable=False),
        sa.CheckConstraint("next_number >= 30", name="ck_contract_number_counter_start"),
    )
    op.execute(sa.text('''
        INSERT INTO "CONTRACT_NUMBER_COUNTER" (template_key, next_number)
        VALUES ('llc_contract', 30), ('zet_contract', 30)
    '''))
    # Old numbers are deliberately not renumbered. At generation time the
    # server skips any already-issued number for the same company, including
    # those issued before this migration.


def downgrade() -> None:
    # Preserve the counters: dropping them would cause previously issued
    # numbers to be re-used after an upgrade. Restoring the old shared series
    # is unsafe; require an explicit administrator-controlled migration.
    raise RuntimeError("Cannot downgrade the independent numbering without risking duplicate numbers")
