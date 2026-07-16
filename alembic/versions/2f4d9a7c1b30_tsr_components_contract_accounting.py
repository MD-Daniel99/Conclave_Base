"""Link modules to TSR and add component/contract accounting metadata.

Revision ID: 2f4d9a7c1b30
Revises: b2c3d4e5f6
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "2f4d9a7c1b30"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    def inspector():
        return sa.inspect(bind)

    module_columns = {column["name"] for column in inspector().get_columns("MODULES")}
    if "tsr_id" not in module_columns:
        op.add_column("MODULES", sa.Column("tsr_id", postgresql.UUID(as_uuid=True), nullable=True))

    module_indexes = {index["name"] for index in inspector().get_indexes("MODULES")}
    if "ix_MODULES_tsr_id" not in module_indexes:
        op.create_index("ix_MODULES_tsr_id", "MODULES", ["tsr_id"], unique=False)

    module_foreign_keys = inspector().get_foreign_keys("MODULES")
    has_tsr_foreign_key = any(fk.get("constrained_columns") == ["tsr_id"] for fk in module_foreign_keys)
    if not has_tsr_foreign_key:
        op.create_foreign_key(
            "fk_modules_tsr_id_ref_tsr",
            "MODULES",
            "REF_TSR",
            ["tsr_id"],
            ["tsr_id"],
            ondelete="RESTRICT",
        )

    document_columns = {column["name"] for column in inspector().get_columns("DOCUMENT")}
    document_additions = {
        "document_type": sa.Column("document_type", sa.String(length=64), nullable=True),
        "document_number": sa.Column("document_number", sa.String(length=64), nullable=True),
        "contract_total": sa.Column("contract_total", sa.Float(), nullable=True),
        "certificate_amount": sa.Column("certificate_amount", sa.Float(), nullable=True),
        "contract_metadata": sa.Column("contract_metadata", sa.JSON(), nullable=True),
    }
    for name, column in document_additions.items():
        if name not in document_columns:
            op.add_column("DOCUMENT", column)

    document_indexes = {index["name"] for index in inspector().get_indexes("DOCUMENT")}
    if "ix_DOCUMENT_document_type" not in document_indexes:
        op.create_index("ix_DOCUMENT_document_type", "DOCUMENT", ["document_type"], unique=False)

    table_names = set(inspector().get_table_names())
    if "MODULE_COMPONENT" not in table_names:
        op.create_table(
            "MODULE_COMPONENT",
            sa.Column("component_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("module_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("component_index", sa.String(length=128), nullable=False),
            sa.Column("supplier", sa.String(length=128), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("cost", sa.Float(), nullable=False, server_default="0"),
            sa.Column("price", sa.Float(), nullable=False, server_default="0"),
            sa.Column("ordered", sa.String(length=64), nullable=False, server_default="0"),
            sa.Column("received", sa.String(length=64), nullable=False, server_default="0"),
            sa.Column("pending", sa.String(length=64), nullable=False, server_default="0"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["module_id"], ["MODULES.module_id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("component_id"),
        )
    component_indexes = {index["name"] for index in inspector().get_indexes("MODULE_COMPONENT")}
    if "ix_MODULE_COMPONENT_module_id" not in component_indexes:
        op.create_index("ix_MODULE_COMPONENT_module_id", "MODULE_COMPONENT", ["module_id"], unique=False)

    table_names = set(inspector().get_table_names())
    if "CONTRACT_ACCOUNTING" not in table_names:
        op.create_table(
            "CONTRACT_ACCOUNTING",
            sa.Column("accounting_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("prosthetist_work", sa.Float(), nullable=False, server_default="0"),
            sa.Column("patient_travel", sa.Float(), nullable=False, server_default="0"),
            sa.Column("patient_accommodation", sa.Float(), nullable=False, server_default="0"),
            sa.Column("patient_payment", sa.Float(), nullable=False, server_default="0"),
            sa.Column("other_expenses", sa.Float(), nullable=False, server_default="0"),
            sa.Column("agency_expenses", sa.Float(), nullable=False, server_default="0"),
            sa.Column("custom_values", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["document_id"], ["DOCUMENT.document_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("accounting_id"),
            sa.UniqueConstraint("document_id"),
        )
    accounting_indexes = {index["name"] for index in inspector().get_indexes("CONTRACT_ACCOUNTING")}
    if "ix_CONTRACT_ACCOUNTING_document_id" not in accounting_indexes:
        op.create_index("ix_CONTRACT_ACCOUNTING_document_id", "CONTRACT_ACCOUNTING", ["document_id"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    table_names = set(sa.inspect(bind).get_table_names())
    if "CONTRACT_ACCOUNTING" in table_names:
        op.drop_table("CONTRACT_ACCOUNTING")
    if "MODULE_COMPONENT" in table_names:
        op.drop_table("MODULE_COMPONENT")

    document_columns = {column["name"] for column in sa.inspect(bind).get_columns("DOCUMENT")}
    for column in ("contract_metadata", "certificate_amount", "contract_total", "document_number", "document_type"):
        if column in document_columns:
            op.drop_column("DOCUMENT", column)

    module_foreign_keys = sa.inspect(bind).get_foreign_keys("MODULES")
    for foreign_key in module_foreign_keys:
        if foreign_key.get("constrained_columns") == ["tsr_id"] and foreign_key.get("name"):
            op.drop_constraint(foreign_key["name"], "MODULES", type_="foreignkey")
    module_columns = {column["name"] for column in sa.inspect(bind).get_columns("MODULES")}
    if "tsr_id" in module_columns:
        op.drop_column("MODULES", "tsr_id")
