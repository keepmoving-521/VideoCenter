"""Add unified background task model.

Revision ID: 73e2b8f940a1
Revises: 9d4c7a21b6e0
Create Date: 2026-06-22 01:15:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "73e2b8f940a1"
down_revision: str | Sequence[str] | None = "9d4c7a21b6e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "background_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "task_type",
            sa.Enum(
                "DOWNLOAD",
                "MEDIA_SCAN",
                "MEDIA_ANALYSIS",
                "HLS_TRANSCODE",
                "GENERIC",
                name="backgroundtasktype",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "WAITING",
                "RUNNING",
                "PAUSED",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                name="backgroundtaskstatus",
            ),
            server_default="WAITING",
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("source_task_id", sa.Integer(), nullable=True),
        sa.Column("parent_task_id", sa.Integer(), nullable=True),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("progress", sa.Float(), server_default="0", nullable=False),
        sa.Column("processed_items", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_items", sa.Integer(), nullable=True),
        sa.Column("attempt", sa.Integer(), server_default="1", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="1", nullable=False),
        sa.Column("cancellable", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("pause_supported", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("worker_id", sa.String(255), nullable=True),
        sa.Column("task_payload", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("task_result", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "attempt >= 1 AND max_attempts >= 1 AND attempt <= max_attempts",
            name="ck_background_task_attempt_range",
        ),
        sa.CheckConstraint(
            "priority >= -100 AND priority <= 100",
            name="ck_background_task_priority_range",
        ),
        sa.CheckConstraint(
            "processed_items >= 0",
            name="ck_background_task_processed_non_negative",
        ),
        sa.CheckConstraint(
            "total_items IS NULL OR processed_items <= total_items",
            name="ck_background_task_processed_not_above_total",
        ),
        sa.CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="ck_background_task_progress_range",
        ),
        sa.CheckConstraint(
            "total_items IS NULL OR total_items >= 0",
            name="ck_background_task_total_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["parent_task_id"],
            ["background_tasks.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_type",
            "source_task_id",
            name="uq_background_task_type_source",
        ),
    )
    with op.batch_alter_table("background_tasks") as batch_op:
        for column in (
            "heartbeat_at",
            "parent_task_id",
            "priority",
            "status",
            "task_type",
            "worker_id",
        ):
            batch_op.create_index(batch_op.f(f"ix_background_tasks_{column}"), [column])


def downgrade() -> None:
    with op.batch_alter_table("background_tasks") as batch_op:
        for column in (
            "worker_id",
            "task_type",
            "status",
            "priority",
            "parent_task_id",
            "heartbeat_at",
        ):
            batch_op.drop_index(batch_op.f(f"ix_background_tasks_{column}"))
    op.drop_table("background_tasks")
