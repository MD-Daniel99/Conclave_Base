"""Keep every generated contract, including several contracts for one TSR.

Revision ID: 7b6e20261109
Revises: 4e8b20261103

The former partial unique index deleted/rejected older contracts. This change
only drops that uniqueness restriction; no patient, document or accounting row
is deleted or rewritten.
"""
from alembic import op
import sqlalchemy as sa

revision = "7b6e20261109"
down_revision = "4e8b20261103"
branch_labels = None
depends_on = None

INDEX = "uq_document_current_contract_per_certificate"


def upgrade():
    op.execute(sa.text(f'DROP INDEX IF EXISTS "{INDEX}"'))
    # ix_DOCUMENT_certificate_id (non-unique) is already present from the old
    # migration; keep it for regular certificate lookups.


def downgrade():
    bind = op.get_bind()
    duplicate = bind.execute(sa.text('''
        SELECT certificate_id FROM "DOCUMENT"
        WHERE certificate_id IS NOT NULL
          AND document_type IN ('llc_contract', 'dmk_contract', 'sdv_contract')
        GROUP BY certificate_id HAVING COUNT(*) > 1 LIMIT 1
    ''')).first()
    if duplicate:
        raise RuntimeError(
            "Cannot restore one-contract-per-TSR index without losing documents; "
            "delete duplicate contracts deliberately before downgrade."
        )
    op.execute(sa.text(f'''
        CREATE UNIQUE INDEX IF NOT EXISTS "{INDEX}"
        ON "DOCUMENT" (certificate_id)
        WHERE certificate_id IS NOT NULL
          AND document_type IN ('llc_contract', 'dmk_contract', 'sdv_contract')
    '''))
