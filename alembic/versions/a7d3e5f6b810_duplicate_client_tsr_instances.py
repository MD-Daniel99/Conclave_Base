"""Allow duplicate client TSR instances and link components to an instance.

Revision ID: a7d3e5f6b810
Revises: 9f4a1b2c3d70
Create Date: 2026-07-31
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "a7d3e5f6b810"
down_revision: Union[str, Sequence[str], None] = "9f4a1b2c3d70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    client_columns = {column["name"] for column in inspector.get_columns("CLIENT")}
    if "email" not in client_columns:
        op.add_column("CLIENT", sa.Column("email", sa.String(length=64), nullable=True))

    unique_constraints = {
        constraint.get("name")
        for constraint in inspector.get_unique_constraints("CLIENT_TSR")
    }
    if "uq_client_tsr_client_tsr" in unique_constraints:
        op.drop_constraint("uq_client_tsr_client_tsr", "CLIENT_TSR", type_="unique")

    module_columns = {column["name"] for column in inspector.get_columns("MODULES")}
    if "client_tsr_id" not in module_columns:
        op.add_column(
            "MODULES",
            sa.Column("client_tsr_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            "fk_modules_client_tsr_id",
            "MODULES",
            "CLIENT_TSR",
            ["client_tsr_id"],
            ["client_tsr_id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_MODULES_client_tsr_id", "MODULES", ["client_tsr_id"], unique=False)

    # Existing components are assigned to the oldest matching client↔TSR row.
    # New duplicates are distinguished by client_tsr_id from this migration on.
    bind.execute(sa.text('''
        UPDATE "MODULES" AS module
        SET client_tsr_id = (
            SELECT client_tsr.client_tsr_id
            FROM "CLIENT_TSR" AS client_tsr
            WHERE client_tsr.client_id = module.client_id
              AND client_tsr.tsr_id = module.tsr_id
            ORDER BY client_tsr.created_at, client_tsr.client_tsr_id
            LIMIT 1
        )
        WHERE module.client_id IS NOT NULL
          AND module.tsr_id IS NOT NULL
          AND module.client_tsr_id IS NULL
    '''))


def downgrade() -> None:
    # Keep CLIENT.email on downgrade to avoid silently deleting user contact data.
    bind = op.get_bind()
    inspector = inspect(bind)
    module_columns = {column["name"] for column in inspector.get_columns("MODULES")}
    if "client_tsr_id" in module_columns:
        indexes = {index.get("name") for index in inspector.get_indexes("MODULES")}
        if "ix_MODULES_client_tsr_id" in indexes:
            op.drop_index("ix_MODULES_client_tsr_id", table_name="MODULES")
        foreign_keys = {fk.get("name") for fk in inspector.get_foreign_keys("MODULES")}
        if "fk_modules_client_tsr_id" in foreign_keys:
            op.drop_constraint("fk_modules_client_tsr_id", "MODULES", type_="foreignkey")
        op.drop_column("MODULES", "client_tsr_id")

    # A downgrade cannot retain duplicate rows under the old constraint. Keep
    # the oldest instance per client/code and remove only duplicate links that
    # became legal in this revision.
    bind.execute(sa.text('''
        DELETE FROM "CLIENT_TSR" AS duplicate
        USING "CLIENT_TSR" AS keeper
        WHERE duplicate.client_id = keeper.client_id
          AND duplicate.tsr_id = keeper.tsr_id
          AND (
              duplicate.created_at > keeper.created_at
              OR (duplicate.created_at = keeper.created_at AND duplicate.client_tsr_id > keeper.client_tsr_id)
          )
    '''))
    op.create_unique_constraint(
        "uq_client_tsr_client_tsr",
        "CLIENT_TSR",
        ["client_id", "tsr_id"],
    )
