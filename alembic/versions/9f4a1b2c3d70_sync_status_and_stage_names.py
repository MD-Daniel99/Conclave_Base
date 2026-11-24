"""Synchronize status and stage reference names.

Revision ID: 9f4a1b2c3d70
Revises: 8c2f6e4a9b10
Create Date: 2026-07-30
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "9f4a1b2c3d70"
down_revision: Union[str, Sequence[str], None] = "8c2f6e4a9b10"
branch_labels = None
depends_on = None


STATUS_VALUES: tuple[tuple[str, str], ...] = (
    ("new", "Новый"),
    ("work", "В работе"),
    ("fail", "Отказ"),
    ("hold", "Отложен"),
    ("success", "Успешно завершен"),
)

STAGE_VALUES: tuple[tuple[str, str], ...] = (
    ("contact", "Первичный контакт"),
    ("meeting", "Встреча/Переговоры"),
    ("contract", "Договор"),
    ("prepay", "Оплата"),
    ("production", "Протезирование"),
    ("done", "Закрытие актов"),
    ("shipping", "Выполнено"),
)


def _upsert_values(
    table_name: str,
    code_column: str,
    values: tuple[tuple[str, str], ...],
) -> None:
    bind = op.get_bind()
    statement = sa.text(
        f'''\
        INSERT INTO "{table_name}" ("{code_column}", description)
        VALUES (:code, :description)
        ON CONFLICT ("{code_column}")
        DO UPDATE SET description = EXCLUDED.description
        '''
    )
    for code, description in values:
        bind.execute(statement, {"code": code, "description": description})


def _delete_unused_known_legacy_rows() -> None:
    """Удалить только известные старые записи и только если они не используются.

    Пользовательские справочники и ссылки существующих клиентов не затрагиваются.
    """
    bind = op.get_bind()

    bind.execute(
        sa.text(
            '''
            DELETE FROM "STAGE" AS stage
            WHERE stage.stage_code IN (
                'kp',
                'S_INVAL', 'MTZ', 'IPRA', 'WAIT_CERT', 'PROB_CERT',
                'WAIT_PARTS', 'CONTRACT_SENT', 'PROSTHESIS', 'DONE'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM "CLIENT" AS client
                WHERE client.current_stage = stage.stage_code
            )
            '''
        )
    )

    bind.execute(
        sa.text(
            '''
            DELETE FROM "STATUS" AS status
            WHERE status.status_code IN (
                'WORKING', 'IN_PROGRESS', 'CANCELLED', 'DONE'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM "CLIENT" AS client
                WHERE client.status_code = status.status_code
            )
            '''
        )
    )


def upgrade() -> None:
    _upsert_values("STATUS", "status_code", STATUS_VALUES)
    _upsert_values("STAGE", "stage_code", STAGE_VALUES)
    _delete_unused_known_legacy_rows()


def downgrade() -> None:
    # Возвращаем подписи, которые были в исходной версии приложения.
    bind = op.get_bind()
    previous_stage_values = (
        ("contact", "Первичный контакт"),
        ("meeting", "Встреча/Переговоры"),
        ("kp", "Отправлено КП"),
        ("contract", "Договор"),
        ("prepay", "Предоплата"),
        ("production", "В производстве"),
        ("shipping", "Отгрузка"),
        ("done", "Закрытие актов"),
    )
    statement = sa.text(
        '''
        INSERT INTO "STAGE" (stage_code, description)
        VALUES (:code, :description)
        ON CONFLICT (stage_code)
        DO UPDATE SET description = EXCLUDED.description
        '''
    )
    for code, description in previous_stage_values:
        bind.execute(statement, {"code": code, "description": description})
