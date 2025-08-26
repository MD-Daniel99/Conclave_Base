"""seed status and stage

Revision ID: e68e87708dcb
Revises: 6111f3154456
Create Date: 2025-08-15 11:58:36.731115

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e68e87708dcb'
down_revision: Union[str, Sequence[str], None] = '6111f3154456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Вставляем записи в STATUS и STAGE.
    Используем INSERT ... ON CONFLICT DO NOTHING чтобы миграция была идемпотентной —
    можно безопасно запускать повторно (или после отката).
    """
    conn = op.get_bind()

    # Статусы
    conn.execute(
        sa.text(
            """
            INSERT INTO "STATUS" (status_code, description) VALUES
              (:c1, :d1),
              (:c2, :d2),
              (:c3, :d3),
              (:c4, :d4)
            ON CONFLICT (status_code) DO NOTHING;
            """
        ),
        {
            "c1": "WORKING",   "d1": "Работа с документами",
            "c2": "IN_PROGRESS","d2": "Выполняется",
            "c3": "CANCELLED", "d3": "Отменен",
            "c4": "DONE",      "d4": "Выполнено",
        },
    )

    # Этапы
    conn.execute(
        sa.text(
            """
            INSERT INTO "STAGE" (stage_code, description) VALUES
              (:s1, :sd1),
              (:s2, :sd2),
              (:s3, :sd3),
              (:s4, :sd4),
              (:s5, :sd5),
              (:s6, :sd6),
              (:s7, :sd7),
              (:s8, :sd8),
              (:s9, :sd9)
            ON CONFLICT (stage_code) DO NOTHING;
            """
        ),
        {
            "s1": "S_INVAL",       "sd1": "Справка об инвалидности",
            "s2": "MTZ",           "sd2": "МТЗ",
            "s3": "IPRA",          "sd3": "ИПРА",
            "s4": "WAIT_CERT",     "sd4": "Ожидание сертификата",
            "s5": "PROB_CERT",     "sd5": "Пробитие сертификата",
            "s6": "WAIT_PARTS",    "sd6": "Ожидание комплектующих",
            "s7": "CONTRACT_SENT", "sd7": "Договор отправлен на подпись",
            "s8": "PROSTHESIS",    "sd8": "Протезирование",
            "s9": "DONE",          "sd9": "Выполнен",
        },
    )


def downgrade() -> None:
    conn = op.get_bind()
    # удаляем наши seed-записи (если нужно)
    conn.execute(
        sa.text(
            "DELETE FROM \"STATUS\" WHERE status_code IN (:c1,:c2,:c3,:c4)"
        ),
        {"c1": "WORKING", "c2": "IN_PROGRESS", "c3": "CANCELLED", "c4": "DONE"},
    )

    conn.execute(
        sa.text(
            "DELETE FROM \"STAGE\" WHERE stage_code IN (:s1,:s2,:s3,:s4,:s5,:s6,:s7,:s8,:s9)"
        ),
        {
            "s1": "S_INVAL", "s2": "MTZ", "s3": "IPRA", "s4": "WAIT_CERT", "s5": "PROB_CERT",
            "s6": "WAIT_PARTS", "s7": "CONTRACT_SENT", "s8": "PROSTHESIS", "s9": "DONE",
        },
    )
