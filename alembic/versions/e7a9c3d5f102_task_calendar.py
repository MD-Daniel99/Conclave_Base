"""calendar task manager and in-app notifications

Revision ID: e7a9c3d5f102
Revises: d6f8a2c4e901
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e7a9c3d5f102"
down_revision: Union[str, Sequence[str], None] = "d6f8a2c4e901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "TASK",
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_day", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="planned", nullable=False),
        sa.Column("priority", sa.String(length=16), server_default="normal", nullable=False),
        sa.Column("color", sa.String(length=16), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('planned', 'in_progress', 'done', 'cancelled')", name="ck_task_status_allowed"),
        sa.CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name="ck_task_priority_allowed"),
        sa.CheckConstraint("due_at >= start_at", name="ck_task_due_after_start"),
        sa.ForeignKeyConstraint(["created_by"], ["USERS.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("task_id"),
    )
    op.create_index("ix_TASK_start_at", "TASK", ["start_at"], unique=False)
    op.create_index("ix_TASK_due_at", "TASK", ["due_at"], unique=False)
    op.create_index("ix_TASK_status", "TASK", ["status"], unique=False)
    op.create_index("ix_TASK_priority", "TASK", ["priority"], unique=False)
    op.create_index("ix_TASK_created_by", "TASK", ["created_by"], unique=False)

    op.create_table(
        "TASK_ASSIGNEE",
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["assigned_by"], ["USERS.user_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["TASK.task_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["USERS.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("task_id", "user_id"),
    )
    op.create_index("ix_TASK_ASSIGNEE_user_id", "TASK_ASSIGNEE", ["user_id"], unique=False)

    op.create_table(
        "TASK_NOTIFICATION",
        sa.Column("notification_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["TASK.task_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["USERS.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("notification_id"),
        sa.UniqueConstraint("task_id", "user_id", "kind", name="uq_task_notification_task_user_kind"),
    )
    op.create_index("ix_TASK_NOTIFICATION_user_id", "TASK_NOTIFICATION", ["user_id"], unique=False)
    op.create_index("ix_TASK_NOTIFICATION_task_id", "TASK_NOTIFICATION", ["task_id"], unique=False)
    op.create_index("ix_TASK_NOTIFICATION_created_at", "TASK_NOTIFICATION", ["created_at"], unique=False)
    op.create_index("ix_TASK_NOTIFICATION_read_at", "TASK_NOTIFICATION", ["read_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_TASK_NOTIFICATION_read_at", table_name="TASK_NOTIFICATION")
    op.drop_index("ix_TASK_NOTIFICATION_created_at", table_name="TASK_NOTIFICATION")
    op.drop_index("ix_TASK_NOTIFICATION_task_id", table_name="TASK_NOTIFICATION")
    op.drop_index("ix_TASK_NOTIFICATION_user_id", table_name="TASK_NOTIFICATION")
    op.drop_table("TASK_NOTIFICATION")

    op.drop_index("ix_TASK_ASSIGNEE_user_id", table_name="TASK_ASSIGNEE")
    op.drop_table("TASK_ASSIGNEE")

    op.drop_index("ix_TASK_created_by", table_name="TASK")
    op.drop_index("ix_TASK_priority", table_name="TASK")
    op.drop_index("ix_TASK_status", table_name="TASK")
    op.drop_index("ix_TASK_due_at", table_name="TASK")
    op.drop_index("ix_TASK_start_at", table_name="TASK")
    op.drop_table("TASK")
