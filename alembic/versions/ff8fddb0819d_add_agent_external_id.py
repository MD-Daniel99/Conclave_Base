"""add agent.external_id with sequences (improved)

Revision ID: ff8fddb0819d
Revises: 91dc45dc898a
Create Date: 2025-08-19 12:35:08.318159
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff8fddb0819d'
down_revision: Union[str, Sequence[str], None] = '91dc45dc898a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1) Создаём последовательности, если их ещё нет
    op.execute("CREATE SEQUENCE IF NOT EXISTS agent_external_id_seq START 1;")
    op.execute("CREATE SEQUENCE IF NOT EXISTS client_external_id_seq START 1;")

    # 2) Добавляем столбцы с server_default nextval(...). Это присвоит существующим строкам значения.
    op.add_column(
        'AGENT',
        sa.Column(
            'external_id',
            sa.BigInteger(),
            server_default=sa.text("nextval('agent_external_id_seq'::regclass)"),
            nullable=False,
        ),
    )
    op.create_unique_constraint('uq_agent_external_id', 'AGENT', ['external_id'])

    op.add_column(
        'CLIENT',
        sa.Column(
            'external_id',
            sa.BigInteger(),
            server_default=sa.text("nextval('client_external_id_seq'::regclass)"),
            nullable=False,
        ),
    )
    op.create_unique_constraint('uq_client_external_id', 'CLIENT', ['external_id'])

    # 3) Устанавливаем sequence в безопасное значение: max(existing) + 1
    #    Так мы гарантируем, что следующие nextval() не вернут уже существующие external_id.
    op.execute(
        "SELECT setval('agent_external_id_seq', (SELECT COALESCE(MAX(external_id), 0) + 1 FROM \"AGENT\"), false);"
    )
    op.execute(
        "SELECT setval('client_external_id_seq', (SELECT COALESCE(MAX(external_id), 0) + 1 FROM \"CLIENT\"), false);"
    )

    # 4) Привязываем последовательности к столбцам (OWNED BY)
    op.execute('ALTER SEQUENCE agent_external_id_seq OWNED BY "AGENT".external_id;')
    op.execute('ALTER SEQUENCE client_external_id_seq OWNED BY "CLIENT".external_id;')


def downgrade() -> None:
    """Downgrade schema."""
    # 1) Удаляем уникальные ограничения и колонки
    op.drop_constraint('uq_client_external_id', 'CLIENT', type_='unique')
    op.drop_column('CLIENT', 'external_id')

    op.drop_constraint('uq_agent_external_id', 'AGENT', type_='unique')
    op.drop_column('AGENT', 'external_id')

    # 2) Удаляем последовательности (если они были созданы этим файлом)
    op.execute("DROP SEQUENCE IF EXISTS client_external_id_seq;")
    op.execute("DROP SEQUENCE IF EXISTS agent_external_id_seq;")
