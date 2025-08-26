"""Normalize name cols agent/client

Revision ID: 6111f3154456
Revises: a153cb9a67fc
Create Date: 2025-08-14 15:21:40.753625

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6111f3154456'
down_revision: Union[str, Sequence[str], None] = 'a153cb9a67fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
