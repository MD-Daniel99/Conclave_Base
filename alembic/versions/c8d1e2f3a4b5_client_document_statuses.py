"""Add selectable contract and act statuses to clients.

Revision ID: c8d1e2f3a4b5
Revises: b831a4e7c201
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8d1e2f3a4b5"
down_revision: Union[str, Sequence[str], None] = "b831a4e7c201"
branch_labels = None
depends_on = None


ALLOWED_STATUSES = ("Подписан", "Сделан", "Отправлен")
STATUS_COLUMNS = ("contract_status", "act_status")
CONSTRAINTS = {
    "contract_status": "ck_client_contract_status_allowed",
    "act_status": "ck_client_act_status_allowed",
}


def _column_names(bind) -> set[str]:
    return {
        column["name"]
        for column in sa.inspect(bind).get_columns("CLIENT")
    }


def _check_names(bind) -> set[str]:
    return {
        constraint["name"]
        for constraint in sa.inspect(bind).get_check_constraints("CLIENT")
        if constraint.get("name")
    }


def _normalize_legacy_column(bind, column_name: str) -> None:
    bind.execute(
        sa.text(
            f'''
            UPDATE "CLIENT"
            SET {column_name} = CASE
                WHEN lower(btrim({column_name})) = 'подписан' THEN 'Подписан'
                WHEN lower(btrim({column_name})) IN ('сделан', 'сделана', 'сделано', 'сделала') THEN 'Сделан'
                WHEN lower(btrim({column_name})) LIKE '%отправлен%' THEN 'Отправлен'
                ELSE NULL
            END
            WHERE {column_name} IS NOT NULL
            '''
        )
    )


def _backfill_from_import_notes(bind) -> None:
    # Старый импорт сохранил исходные статусы только внутри заметок пациента.
    # Переносим лишь однозначно распознаваемые значения; остальные заметки не
    # меняем и не пытаемся интерпретировать автоматически.
    bind.execute(
        sa.text(
            '''
            UPDATE "CLIENT"
            SET contract_status = CASE
                WHEN contract_status IS NOT NULL THEN contract_status
                WHEN lower(notes) LIKE '%статус договора: подписан.%' THEN 'Подписан'
                WHEN lower(notes) LIKE '%статус договора: сделан.%'
                  OR lower(notes) LIKE '%статус договора: сделана.%'
                  OR lower(notes) LIKE '%статус договора: сделала.%' THEN 'Сделан'
                WHEN lower(notes) LIKE '%статус договора: отправлен%' THEN 'Отправлен'
                ELSE contract_status
            END,
            act_status = CASE
                WHEN act_status IS NOT NULL THEN act_status
                WHEN lower(notes) LIKE '%статус актов: подписан.%' THEN 'Подписан'
                WHEN lower(notes) LIKE '%статус актов: сделан.%'
                  OR lower(notes) LIKE '%статус актов: сделана.%'
                  OR lower(notes) LIKE '%статус актов: сделала.%' THEN 'Сделан'
                WHEN lower(notes) LIKE '%статус актов: отправлен%' THEN 'Отправлен'
                ELSE act_status
            END
            WHERE notes IS NOT NULL
              AND (contract_status IS NULL OR act_status IS NULL)
            '''
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    if "CLIENT" not in set(sa.inspect(bind).get_table_names()):
        raise RuntimeError('Expected table "CLIENT" is absent')

    existing_columns = _column_names(bind)
    for column_name in STATUS_COLUMNS:
        if column_name not in existing_columns:
            op.add_column(
                "CLIENT",
                sa.Column(column_name, sa.String(length=32), nullable=True),
            )

    for column_name in STATUS_COLUMNS:
        _normalize_legacy_column(bind, column_name)
    _backfill_from_import_notes(bind)

    existing_checks = _check_names(bind)
    allowed_sql = ", ".join(f"'{value}'" for value in ALLOWED_STATUSES)
    for column_name, constraint_name in CONSTRAINTS.items():
        if constraint_name not in existing_checks:
            op.create_check_constraint(
                constraint_name,
                "CLIENT",
                f"{column_name} IS NULL OR {column_name} IN ({allowed_sql})",
            )


def downgrade() -> None:
    bind = op.get_bind()
    if "CLIENT" not in set(sa.inspect(bind).get_table_names()):
        return

    existing_checks = _check_names(bind)
    for constraint_name in CONSTRAINTS.values():
        if constraint_name in existing_checks:
            op.drop_constraint(constraint_name, "CLIENT", type_="check")

    existing_columns = _column_names(bind)
    for column_name in reversed(STATUS_COLUMNS):
        if column_name in existing_columns:
            op.drop_column("CLIENT", column_name)
