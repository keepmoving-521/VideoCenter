"""Add background task logs.

Revision ID: a8c31f72d590
Revises: 4b6d19ea83f2
Create Date: 2026-06-22 22:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8c31f72d590"
down_revision: str | Sequence[str] | None = "4b6d19ea83f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "background_task_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("event", sa.String(100), nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
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
            nullable=True,
        ),
        sa.Column("progress", sa.Float(), nullable=True),
        sa.Column("details", sa.JSON(), server_default="{}", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["background_tasks.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("background_task_logs") as batch_op:
        for column in ("created_at", "event", "status", "task_id"):
            batch_op.create_index(
                batch_op.f(f"ix_background_task_logs_{column}"),
                [column],
            )


def downgrade() -> None:
    with op.batch_alter_table("background_task_logs") as batch_op:
        for column in ("task_id", "status", "event", "created_at"):
            batch_op.drop_index(batch_op.f(f"ix_background_task_logs_{column}"))
    op.drop_table("background_task_logs")
