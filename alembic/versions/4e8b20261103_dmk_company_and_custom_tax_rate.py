"""Allow ИП ДМК patients and store their individual tax rate.

Revision ID: 4e8b20261103
Revises: c9f0a1b2c3d4

This migration changes only schema constraints and adds a nullable column.
It never updates, deletes or resets existing CLIENT data.
"""

from alembic import op
import sqlalchemy as sa

revision = "4e8b20261103"
down_revision = "c9f0a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Safe if the column was created manually before applying this migration.
    op.execute(sa.text(
        'ALTER TABLE "CLIENT" ADD COLUMN IF NOT EXISTS tax_percent_override DOUBLE PRECISION'
    ))
    # The old constraint only knew the two LLCs, causing PostgreSQL CheckViolation
    # (HTTP 500) whenever a patient was assigned to ИП ДМК.
    op.execute(sa.text(
        'ALTER TABLE "CLIENT" DROP CONSTRAINT IF EXISTS ck_client_performer_company_allowed'
    ))
    op.execute(sa.text('''
        ALTER TABLE "CLIENT" ADD CONSTRAINT ck_client_performer_company_allowed
        CHECK (
            performer_company IS NULL
            OR performer_company IN (
                'ООО «ПрОП ДВИЖЕНИЕ ЗЕТ»', 'ООО "Смарт Движение"', 'ИП ДМК'
            )
        )
    '''))
    # If an administrator installed the new column/constraint manually,
    # do not fail the migration halfway through. PostgreSQL has no native
    # ADD CONSTRAINT IF NOT EXISTS, so guard the existing definition.
    op.execute(sa.text('''
        DO $$ BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
             WHERE conname = 'ck_client_tax_percent_override_range'
               AND conrelid = '"CLIENT"'::regclass
          ) THEN
            ALTER TABLE "CLIENT" ADD CONSTRAINT ck_client_tax_percent_override_range
            CHECK (tax_percent_override IS NULL
                   OR (tax_percent_override >= 0 AND tax_percent_override <= 100));
          END IF;
        END $$
    '''))


def downgrade() -> None:
    # Restoring the former two-company check would reject any existing ИП ДМК
    # records. Refuse rather than silently erase or reassign patient data.
    bind = op.get_bind()
    dmk_count = bind.execute(sa.text(
        'SELECT COUNT(*) FROM "CLIENT" WHERE performer_company = :company'
    ), {"company": "ИП ДМК"}).scalar_one()
    if dmk_count:
        raise RuntimeError("Cannot downgrade: ИП ДМК patients exist; backup and migrate them first")
    op.execute(sa.text(
        'ALTER TABLE "CLIENT" DROP CONSTRAINT IF EXISTS ck_client_tax_percent_override_range'
    ))
    op.execute(sa.text(
        'ALTER TABLE "CLIENT" DROP CONSTRAINT IF EXISTS ck_client_performer_company_allowed'
    ))
    op.execute(sa.text('''
        ALTER TABLE "CLIENT" ADD CONSTRAINT ck_client_performer_company_allowed
        CHECK (
            performer_company IS NULL
            OR performer_company IN (
                'ООО «ПрОП ДВИЖЕНИЕ ЗЕТ»', 'ООО "Смарт Движение"'
            )
        )
    '''))
    op.execute(sa.text('ALTER TABLE "CLIENT" DROP COLUMN tax_percent_override'))
