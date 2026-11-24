"""Client TSR assignments and client-card cleanup.

Revision ID: 8c2f6e4a9b10
Revises: 7b91c4e2d6a0
Create Date: 2026-07-30
"""
from __future__ import annotations

import re
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "8c2f6e4a9b10"
down_revision: Union[str, Sequence[str], None] = "7b91c4e2d6a0"
branch_labels = None
depends_on = None


def _columns(inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

    if "CLIENT_TSR" not in table_names:
        op.create_table(
            "CLIENT_TSR",
            sa.Column("client_tsr_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("tsr_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("check_date", sa.Date(), nullable=True),
            sa.Column("certificate_price", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["client_id"], ["CLIENT.client_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tsr_id"], ["REF_TSR.tsr_id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("client_tsr_id"),
            sa.UniqueConstraint("client_id", "tsr_id", name="uq_client_tsr_client_tsr"),
        )
        op.create_index("ix_CLIENT_TSR_client_id", "CLIENT_TSR", ["client_id"], unique=False)
        op.create_index("ix_CLIENT_TSR_tsr_id", "CLIENT_TSR", ["tsr_id"], unique=False)

    # Normalize the fields that were partially changed in the application code.
    client_columns = _columns(inspect(bind), "CLIENT")
    if "taxation_system" in client_columns:
        bind.execute(sa.text('''
            UPDATE "CLIENT"
            SET taxation_system = 'УСН'
            WHERE taxation_system IS NULL
               OR taxation_system NOT IN ('УСН', 'ОСНО')
        '''))
        op.alter_column(
            "CLIENT",
            "taxation_system",
            existing_type=sa.String(length=4),
            type_=sa.String(length=16),
            existing_nullable=False,
            server_default=sa.text("'УСН'"),
        )
    if "place_of_residence" in client_columns:
        op.alter_column(
            "CLIENT",
            "place_of_residence",
            existing_type=sa.String(length=64),
            type_=sa.String(length=255),
            existing_nullable=True,
        )
    if "prosthetist" in client_columns:
        # The new UI accepts only two specialists. Unknown legacy values are
        # cleared instead of failing the VARCHAR(32) conversion or receiving
        # an address that belongs to another specialist.
        bind.execute(sa.text('''
            UPDATE "CLIENT"
            SET prosthetist = NULL
            WHERE prosthetist IS NOT NULL
              AND prosthetist NOT IN ('Дмитрий', 'Никита')
        '''))
        op.alter_column(
            "CLIENT",
            "prosthetist",
            existing_type=sa.Text(),
            type_=sa.String(length=32),
            existing_nullable=True,
            server_default=None,
        )
        bind.execute(sa.text('''
            UPDATE "CLIENT"
            SET place_of_residence = CASE prosthetist
                WHEN 'Дмитрий' THEN 'Ивана Сусанина, д. 3'
                WHEN 'Никита' THEN 'Большая Почтовая, д. 18/20'
                ELSE NULL
            END
        '''))

    existing_checks = {
        constraint.get("name")
        for constraint in inspect(bind).get_check_constraints("CLIENT")
    }
    if not {"ck_client_taxation_system_allowed", "ck_CLIENT_taxation_system"}.intersection(existing_checks):
        op.create_check_constraint(
            "ck_client_taxation_system_allowed",
            "CLIENT",
            "taxation_system IN ('УСН', 'ОСНО')",
        )
    if "ck_client_prosthetist_allowed" not in existing_checks:
        op.create_check_constraint(
            "ck_client_prosthetist_allowed",
            "CLIENT",
            "prosthetist IS NULL OR prosthetist IN ('Дмитрий', 'Никита')",
        )
    if "ck_client_prosthetist_address" not in existing_checks:
        op.create_check_constraint(
            "ck_client_prosthetist_address",
            "CLIENT",
            "(prosthetist IS NULL AND place_of_residence IS NULL) OR "
            "(prosthetist = 'Дмитрий' AND place_of_residence = 'Ивана Сусанина, д. 3') OR "
            "(prosthetist = 'Никита' AND place_of_residence = 'Большая Почтовая, д. 18/20')",
        )

    passport_columns = _columns(inspect(bind), "PASSPORT")
    if "expiry_date" in passport_columns:
        op.drop_column("PASSPORT", "expiry_date")

    # Backfill explicit client↔TSR links from both warehouse components and the legacy text field.
    ref_rows = bind.execute(sa.text('SELECT tsr_id, full_tsr_code FROM "REF_TSR"')).mappings().all()
    refs_by_full = {
        str(row["full_tsr_code"] or "").strip(): row["tsr_id"]
        for row in ref_rows
        if str(row["full_tsr_code"] or "").strip()
    }
    refs_by_code: dict[str, object] = {}
    for full, tsr_id in refs_by_full.items():
        match = re.match(r"^\s*(\d{1,2}-\d{2}(?:[-.\d]*)?)", full)
        if match and match.group(1) not in refs_by_code:
            refs_by_code[match.group(1)] = tsr_id

    existing_pairs = {
        (row["client_id"], row["tsr_id"])
        for row in bind.execute(sa.text('SELECT client_id, tsr_id FROM "CLIENT_TSR"')).mappings()
    }
    component_pairs = bind.execute(sa.text('''
        SELECT DISTINCT client_id, tsr_id
        FROM "MODULES"
        WHERE client_id IS NOT NULL AND tsr_id IS NOT NULL
    ''')).mappings().all()

    def insert_pair(client_id, tsr_id) -> None:
        pair = (client_id, tsr_id)
        if pair in existing_pairs:
            return
        bind.execute(
            sa.text('''
                INSERT INTO "CLIENT_TSR"
                    (client_tsr_id, client_id, tsr_id, created_at, updated_at)
                VALUES (:id, :client_id, :tsr_id, now(), now())
            '''),
            {"id": uuid.uuid4(), "client_id": client_id, "tsr_id": tsr_id},
        )
        existing_pairs.add(pair)

    for row in component_pairs:
        insert_pair(row["client_id"], row["tsr_id"])

    clients = bind.execute(
        sa.text('SELECT client_id, tsr_code, certificate_price, check_date FROM "CLIENT"')
    ).mappings().all()
    for client in clients:
        raw_lines = [line.strip() for line in str(client["tsr_code"] or "").splitlines() if line.strip()]
        for line in raw_lines:
            tsr_id = refs_by_full.get(line)
            if tsr_id is None:
                match = re.match(r"^\s*(\d{1,2}-\d{2}(?:[-.\d]*)?)", line)
                tsr_id = refs_by_code.get(match.group(1)) if match else None
            if tsr_id is not None:
                insert_pair(client["client_id"], tsr_id)

        # Preserve the old single certificate total on one link. Users can split it per TSR later.
        certificate_price = str(client["certificate_price"] or "").strip()
        if certificate_price:
            bind.execute(
                sa.text('''
                    UPDATE "CLIENT_TSR"
                    SET certificate_price = :price
                    WHERE client_tsr_id = (
                        SELECT client_tsr_id FROM "CLIENT_TSR"
                        WHERE client_id = :client_id
                        ORDER BY created_at, client_tsr_id
                        LIMIT 1
                    )
                    AND certificate_price IS NULL
                '''),
                {"client_id": client["client_id"], "price": certificate_price},
            )
        if client["check_date"] is not None:
            bind.execute(
                sa.text('''
                    UPDATE "CLIENT_TSR"
                    SET check_date = :check_date
                    WHERE client_id = :client_id
                    AND check_date IS NULL
                '''),
                {"client_id": client["client_id"], "check_date": client["check_date"]},
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "CLIENT_TSR" in inspector.get_table_names():
        op.drop_index("ix_CLIENT_TSR_tsr_id", table_name="CLIENT_TSR")
        op.drop_index("ix_CLIENT_TSR_client_id", table_name="CLIENT_TSR")
        op.drop_table("CLIENT_TSR")
    existing_checks = {
        constraint.get("name")
        for constraint in inspect(bind).get_check_constraints("CLIENT")
    }
    for constraint_name in (
        "ck_client_prosthetist_address",
        "ck_client_prosthetist_allowed",
        "ck_client_taxation_system_allowed",
    ):
        if constraint_name in existing_checks:
            op.drop_constraint(constraint_name, "CLIENT", type_="check")
    if "expiry_date" not in _columns(inspect(bind), "PASSPORT"):
        op.add_column("PASSPORT", sa.Column("expiry_date", sa.Date(), nullable=True))
