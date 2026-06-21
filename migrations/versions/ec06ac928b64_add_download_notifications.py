"""Add download completion notifications.

Revision ID: ec06ac928b64
Revises: df3d06a94df5
Create Date: 2026-06-21 04:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ec06ac928b64"
down_revision: str | Sequence[str] | None = "df3d06a94df5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "notification_type",
            sa.Enum("DOWNLOAD_COMPLETED", name="notificationtype"),
            nullable=False,
        ),
        sa.Column("download_task_id", sa.Integer(), nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["download_task_id"],
            ["download_tasks.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("download_task_id"),
    )
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_notifications_created_at"),
            ["created_at"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_notifications_download_task_id"),
            ["download_task_id"],
            unique=True,
        )
        batch_op.create_index(
            batch_op.f("ix_notifications_media_id"),
            ["media_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_notifications_notification_type"),
            ["notification_type"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_notifications_read_at"),
            ["read_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_index(batch_op.f("ix_notifications_read_at"))
        batch_op.drop_index(batch_op.f("ix_notifications_notification_type"))
        batch_op.drop_index(batch_op.f("ix_notifications_media_id"))
        batch_op.drop_index(batch_op.f("ix_notifications_download_task_id"))
        batch_op.drop_index(batch_op.f("ix_notifications_created_at"))
    op.drop_table("notifications")
