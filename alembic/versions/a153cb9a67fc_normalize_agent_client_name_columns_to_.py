"""Normalize Agent/Client name columns to varchar(128) and set not null

Revision ID: a153cb9a67fc
Revises: 540c2b87d359
Create Date: 2025-08-14 15:00:51.694218

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a153cb9a67fc'
down_revision: Union[str, Sequence[str], None] = '540c2b87d359'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1) Приводим типы к VARCHAR(128), безопасно усечём длинные значения
    op.execute('ALTER TABLE "AGENT" ALTER COLUMN last_name TYPE VARCHAR(128) USING left(last_name,128);')
    op.execute('ALTER TABLE "AGENT" ALTER COLUMN first_name TYPE VARCHAR(128) USING left(first_name,128);')
    op.execute('ALTER TABLE "AGENT" ALTER COLUMN middle_name TYPE VARCHAR(128) USING left(middle_name,128);')

    # То же для CLIENT
    op.execute('ALTER TABLE "CLIENT" ALTER COLUMN last_name TYPE VARCHAR(128) USING left(last_name,128);')
    op.execute('ALTER TABLE "CLIENT" ALTER COLUMN first_name TYPE VARCHAR(128) USING left(first_name,128);')
    op.execute('ALTER TABLE "CLIENT" ALTER COLUMN middle_name TYPE VARCHAR(128) USING left(middle_name,128);')

    # 2) Заполнение NULL пустой строкой.
    #    Если не хотите, закомментируйте эти строки и НЕ переводите в NOT NULL.
    op.execute("UPDATE \"AGENT\" SET first_name = '' WHERE first_name IS NULL;")
    op.execute("UPDATE \"AGENT\" SET middle_name = '' WHERE middle_name IS NULL;")
    op.execute("UPDATE \"AGENT\" SET last_name = '' WHERE last_name IS NULL;")

    op.execute("UPDATE \"CLIENT\" SET first_name = '' WHERE first_name IS NULL;")
    op.execute("UPDATE \"CLIENT\" SET middle_name = '' WHERE middle_name IS NULL;")
    op.execute("UPDATE \"CLIENT\" SET last_name = '' WHERE last_name IS NULL;")

    # 3) Устанавливаем NOT NULL
    op.alter_column('AGENT', 'last_name', nullable=False, existing_type=sa.VARCHAR(length=128))
    op.alter_column('AGENT', 'first_name', nullable=False, existing_type=sa.VARCHAR(length=128))
    #op.alter_column('AGENT', 'middle_name', nullable=False, existing_type=sa.VARCHAR(length=128))

    op.alter_column('CLIENT', 'last_name', nullable=False, existing_type=sa.VARCHAR(length=128))
    op.alter_column('CLIENT', 'first_name', nullable=False, existing_type=sa.VARCHAR(length=128))
    #op.alter_column('CLIENT', 'middle_name', nullable=False, existing_type=sa.VARCHAR(length=128))



def downgrade() -> None:
    """Downgrade schema."""
    # Откат: вернём тип last_name в AGENT к TEXT и позволим NULL для first/middle
    op.execute('ALTER TABLE "AGENT" ALTER COLUMN last_name TYPE TEXT USING last_name;')
    op.alter_column('AGENT', 'first_name', nullable=True, existing_type=sa.VARCHAR(length=128))
    op.alter_column('AGENT', 'middle_name', nullable=True, existing_type=sa.VARCHAR(length=128))

    op.execute('ALTER TABLE "CLIENT" ALTER COLUMN last_name TYPE TEXT USING last_name;')
    op.alter_column('CLIENT', 'first_name', nullable=True, existing_type=sa.VARCHAR(length=128))
    op.alter_column('CLIENT', 'middle_name', nullable=True, existing_type=sa.VARCHAR(length=128))
