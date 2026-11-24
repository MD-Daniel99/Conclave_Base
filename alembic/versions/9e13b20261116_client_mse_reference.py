"""Add free-form MSE reference to patients without modifying older documents.

Revision ID: 9e13b20261116
Revises: 8c30a9e20261110
"""
from alembic import op
import sqlalchemy as sa

revision = '9e13b20261116'
down_revision = '8c30a9e20261110'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('CLIENT', sa.Column('mse_reference', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('CLIENT', 'mse_reference')
