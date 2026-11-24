"""Store prosthetist/repeat visit per TSR and allow first-name-only agents.

Revision ID: c4e8f1a2b390
Revises: a7d3e5f6b810
Create Date: 2026-08-03
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c4e8f1a2b390"
down_revision: Union[str, Sequence[str], None] = "a7d3e5f6b810"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # An agent may be created with only the required first name.
    op.alter_column(
        "AGENT",
        "last_name",
        existing_type=sa.String(length=128),
        nullable=True,
    )

    op.add_column("CLIENT_TSR", sa.Column("prosthetist", sa.String(length=32), nullable=True))
    op.add_column("CLIENT_TSR", sa.Column("place_of_residence", sa.String(length=255), nullable=True))
    op.add_column("CLIENT_TSR", sa.Column("repeat_visit_date", sa.Date(), nullable=True))

    # Existing client-level values are copied to every current TSR assignment.
    # Afterwards every TSR card is edited independently.
    op.execute(
        sa.text(
            '''
            UPDATE "CLIENT_TSR" AS client_tsr
            SET
                prosthetist = CASE
                    WHEN client.prosthetist IN ('Дмитрий', 'Никита') THEN client.prosthetist
                    ELSE NULL
                END,
                place_of_residence = CASE
                    WHEN client.prosthetist = 'Дмитрий' THEN 'Ивана Сусанина, д. 3'
                    WHEN client.prosthetist = 'Никита' THEN 'Большая Почтовая, д. 18/20'
                    ELSE NULL
                END,
                repeat_visit_date = CAST(client.deadline AS date)
            FROM "CLIENT" AS client
            WHERE client.client_id = client_tsr.client_id
            '''
        )
    )

    op.create_check_constraint(
        "ck_client_tsr_prosthetist_allowed",
        "CLIENT_TSR",
        "prosthetist IS NULL OR prosthetist IN ('Дмитрий', 'Никита')",
    )
    op.create_check_constraint(
        "ck_client_tsr_prosthetist_address",
        "CLIENT_TSR",
        "(prosthetist IS NULL AND place_of_residence IS NULL) OR "
        "(prosthetist = 'Дмитрий' AND place_of_residence = 'Ивана Сусанина, д. 3') OR "
        "(prosthetist = 'Никита' AND place_of_residence = 'Большая Почтовая, д. 18/20')",
    )


def downgrade() -> None:
    # Keep the downgrade safe if surname-less agents were created.
    op.execute(sa.text("UPDATE \"AGENT\" SET last_name = '' WHERE last_name IS NULL"))
    op.alter_column(
        "AGENT",
        "last_name",
        existing_type=sa.String(length=128),
        nullable=False,
    )

    op.drop_constraint("ck_client_tsr_prosthetist_address", "CLIENT_TSR", type_="check")
    op.drop_constraint("ck_client_tsr_prosthetist_allowed", "CLIENT_TSR", type_="check")
    op.drop_column("CLIENT_TSR", "repeat_visit_date")
    op.drop_column("CLIENT_TSR", "place_of_residence")
    op.drop_column("CLIENT_TSR", "prosthetist")
