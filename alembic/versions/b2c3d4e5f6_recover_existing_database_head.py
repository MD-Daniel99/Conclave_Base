"""Restore the revision marker already stored in the existing database.

Revision ID: b2c3d4e5f6
Revises: 84ca40f71fa7, 103a14e50ef0

The deployed database is already stamped with this revision, while its source
file was not present in the supplied project.  This no-op compatibility node
restores the Alembic graph; it does not alter application data.
"""
from typing import Sequence, Union


revision: str = "b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = ("84ca40f71fa7", "103a14e50ef0")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
