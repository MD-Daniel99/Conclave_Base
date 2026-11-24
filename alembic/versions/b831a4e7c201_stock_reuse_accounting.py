"""Track components assigned directly from the dedicated Stock tab.

Revision ID: b831a4e7c201
Revises: f3a9c2d1e8b4
Create Date: 2026-08-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b831a4e7c201"
down_revision: Union[str, Sequence[str], None] = 'f3a9c2d1e8b4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("MODULES")}
    if "accounting_cost_excluded" not in columns:
        op.add_column(
            "MODULES",
            sa.Column(
                "accounting_cost_excluded",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
        op.create_index(
            "ix_MODULES_accounting_cost_excluded",
            "MODULES",
            ["accounting_cost_excluded"],
            unique=False,
        )

    # Existing assignments cannot always be reconstructed reliably from
    # old data. We only backfill when the audit log explicitly proves that
    # the current assignment came directly from the dedicated Stock state.
    if "AUDIT_LOG" in set(inspector.get_table_names()):
        op.execute(sa.text("""
            UPDATE "MODULES" AS m
            SET accounting_cost_excluded = COALESCE((
                SELECT CASE
                    WHEN lower(COALESCE(a.details::jsonb #>> '{before,is_in_stock}', 'false')) = 'true'
                    THEN TRUE ELSE FALSE END
                FROM "AUDIT_LOG" AS a
                WHERE a.entity IN ('component', 'module')
                  AND a.entity_id = m.module_id
                  AND a.details IS NOT NULL
                  AND (a.details::jsonb ? 'before')
                  AND (a.details::jsonb ? 'after')
                  AND COALESCE(a.details::jsonb #>> '{after,client_id}', '') = m.client_id::text
                ORDER BY a.timestamp DESC
                LIMIT 1
            ), FALSE)
            WHERE m.client_id IS NOT NULL
        """))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("MODULES")}
    if "accounting_cost_excluded" in columns:
        indexes = {index["name"] for index in inspector.get_indexes("MODULES")}
        if "ix_MODULES_accounting_cost_excluded" in indexes:
            op.drop_index("ix_MODULES_accounting_cost_excluded", table_name="MODULES")
        op.drop_column("MODULES", "accounting_cost_excluded")
