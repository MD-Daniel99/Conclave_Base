"""Enforce one current contract per certificate instance.

Revision ID: d1e2f3a4b5c6
Revises: c4e8f1a2b390
Create Date: 2026-08-04
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "c4e8f1a2b390"
branch_labels = None
depends_on = None

CONTRACT_TYPES_SQL = "('llc_contract', 'dmk_contract', 'sdv_contract')"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("DOCUMENT")}

    if "certificate_id" not in columns:
        op.add_column(
            "DOCUMENT",
            sa.Column("certificate_id", postgresql.UUID(as_uuid=True), nullable=True),
        )

    foreign_keys = {fk.get("name") for fk in inspect(bind).get_foreign_keys("DOCUMENT")}
    if "fk_document_certificate_id" not in foreign_keys:
        op.create_foreign_key(
            "fk_document_certificate_id",
            "DOCUMENT",
            "CLIENT_TSR",
            ["certificate_id"],
            ["client_tsr_id"],
            ondelete="SET NULL",
        )

    indexes = {index.get("name") for index in inspect(bind).get_indexes("DOCUMENT")}
    if "ix_DOCUMENT_certificate_id" not in indexes:
        op.create_index("ix_DOCUMENT_certificate_id", "DOCUMENT", ["certificate_id"], unique=False)

    # Newer generated documents keep the exact CLIENT_TSR id either directly
    # in metadata or inside the one-certificate snapshot. Invalid legacy text
    # is ignored instead of aborting the whole migration with an UUID cast.
    bind.execute(sa.text(r'''
        WITH candidates AS (
            SELECT
                document.document_id,
                document.client_id,
                COALESCE(
                    NULLIF(document.contract_metadata ->> 'certificate_id', ''),
                    CASE
                        WHEN jsonb_typeof(document.contract_metadata::jsonb -> 'selected_tsr_components') = 'array'
                         AND jsonb_array_length(document.contract_metadata::jsonb -> 'selected_tsr_components') = 1
                        THEN NULLIF(
                            document.contract_metadata::jsonb -> 'selected_tsr_components' -> 0 ->> 'client_tsr_id',
                            ''
                        )
                    END
                ) AS raw_certificate_id
            FROM "DOCUMENT" AS document
            WHERE document.certificate_id IS NULL
              AND document.document_type IN ('llc_contract', 'dmk_contract', 'sdv_contract')
        )
        UPDATE "DOCUMENT" AS document
        SET certificate_id = candidates.raw_certificate_id::uuid
        FROM candidates
        WHERE document.document_id = candidates.document_id
          AND candidates.raw_certificate_id ~*
              '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
          AND EXISTS (
                SELECT 1
                FROM "CLIENT_TSR" AS certificate
                WHERE certificate.client_tsr_id = candidates.raw_certificate_id::uuid
                  AND certificate.client_id = candidates.client_id
          )
    '''))

    # When the same certificate was regenerated several times, keep the newest
    # document. CONTRACT_ACCOUNTING rows are removed by ON DELETE CASCADE.
    bind.execute(sa.text('''
        DELETE FROM "DOCUMENT" AS older
        USING "DOCUMENT" AS newer
        WHERE older.certificate_id IS NOT NULL
          AND newer.certificate_id = older.certificate_id
          AND older.document_type IN ('llc_contract', 'dmk_contract', 'sdv_contract')
          AND newer.document_type IN ('llc_contract', 'dmk_contract', 'sdv_contract')
          AND (
                newer.created_at > older.created_at
                OR (
                    newer.created_at = older.created_at
                    AND newer.document_id > older.document_id
                )
          )
    '''))

    indexes = {index.get("name") for index in inspect(bind).get_indexes("DOCUMENT")}
    if "uq_document_current_contract_per_certificate" not in indexes:
        op.create_index(
            "uq_document_current_contract_per_certificate",
            "DOCUMENT",
            ["certificate_id"],
            unique=True,
            postgresql_where=sa.text(
                f"certificate_id IS NOT NULL AND document_type IN {CONTRACT_TYPES_SQL}"
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    indexes = {index.get("name") for index in inspector.get_indexes("DOCUMENT")}
    if "uq_document_current_contract_per_certificate" in indexes:
        op.drop_index("uq_document_current_contract_per_certificate", table_name="DOCUMENT")
    if "ix_DOCUMENT_certificate_id" in indexes:
        op.drop_index("ix_DOCUMENT_certificate_id", table_name="DOCUMENT")

    foreign_keys = {fk.get("name") for fk in inspector.get_foreign_keys("DOCUMENT")}
    if "fk_document_certificate_id" in foreign_keys:
        op.drop_constraint("fk_document_certificate_id", "DOCUMENT", type_="foreignkey")

    columns = {column["name"] for column in inspect(bind).get_columns("DOCUMENT")}
    if "certificate_id" in columns:
        op.drop_column("DOCUMENT", "certificate_id")
