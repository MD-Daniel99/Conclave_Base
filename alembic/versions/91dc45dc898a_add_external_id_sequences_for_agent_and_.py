"""add external_id sequences for agent and client

Revision ID: 91dc45dc898a
Revises: e68e87708dcb
Create Date: 2025-08-19 12:20:05.127589

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '91dc45dc898a'
down_revision: Union[str, Sequence[str], None] = 'e68e87708dcb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
