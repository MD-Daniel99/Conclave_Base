"""unpunched patients workspace

Revision ID: d6f8a2c4e901
Revises: b5e7c9a1d3f4
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d6f8a2c4e901"
down_revision: Union[str, Sequence[str], None] = "b5e7c9a1d3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("CLIENT", sa.Column("workflow_bucket", sa.String(length=16), server_default="unpunched", nullable=False))
    op.add_column("CLIENT", sa.Column("precheck_status", sa.String(length=64), server_default="Работа с документами", nullable=False))
    op.add_column("CLIENT", sa.Column("precheck_stage", sa.String(length=96), server_default="Справка об инвалидности", nullable=False))
    op.add_column("CLIENT", sa.Column("unpunched_custom_values", postgresql.JSON(astext_type=sa.Text()), server_default=sa.text("'{}'::json"), nullable=False))
    op.create_index("ix_CLIENT_workflow_bucket", "CLIENT", ["workflow_bucket"], unique=False)
    # Существующих активных пациентов распределяем по факту пробития сертификата.
    op.execute(sa.text("""
        UPDATE "CLIENT" c
        SET workflow_bucket = 'work'
        WHERE c.is_archived = false
          AND (c.check_date IS NOT NULL OR EXISTS (
              SELECT 1 FROM "CLIENT_TSR" ct
              WHERE ct.client_id = c.client_id AND ct.check_date IS NOT NULL
          ))
    """))
    op.create_table(
        "UNPUNCHED_CUSTOM_FIELD",
        sa.Column("field_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_name", sa.String(length=128), nullable=False),
        sa.Column("field_type", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("field_id"),
        sa.UniqueConstraint("field_name"),
    )


def downgrade() -> None:
    op.drop_table("UNPUNCHED_CUSTOM_FIELD")
    op.drop_index("ix_CLIENT_workflow_bucket", table_name="CLIENT")
    op.drop_column("CLIENT", "unpunched_custom_values")
    op.drop_column("CLIENT", "precheck_stage")
    op.drop_column("CLIENT", "precheck_status")
    op.drop_column("CLIENT", "workflow_bucket")
