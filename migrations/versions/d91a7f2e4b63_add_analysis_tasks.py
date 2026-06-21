"""Add background video analysis tasks.

Revision ID: d91a7f2e4b63
Revises: c8f42e6d1a90
Create Date: 2026-06-21 17:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d91a7f2e4b63"
down_revision: str | Sequence[str] | None = "c8f42e6d1a90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analysis_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("retry_of_task_id", sa.Integer(), nullable=True),
        sa.Column("resource_ids", sa.JSON(), nullable=False),
        sa.Column("force", sa.Boolean(), server_default="0", nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "WAITING",
                "RUNNING",
                "COMPLETED",
                "FAILED",
                name="analysistaskstatus",
            ),
            nullable=False,
        ),
        sa.Column("progress", sa.Float(), server_default="0", nullable=False),
        sa.Column("total_resources", sa.Integer(), server_default="0", nullable=False),
        sa.Column("processed_resources", sa.Integer(), server_default="0", nullable=False),
        sa.Column("analyzed_resource_ids", sa.JSON(), nullable=False),
        sa.Column("skipped_resource_ids", sa.JSON(), nullable=False),
        sa.Column("missing_resource_ids", sa.JSON(), nullable=False),
        sa.Column("failures", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["retry_of_task_id"], ["analysis_tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("analysis_tasks") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_analysis_tasks_retry_of_task_id"),
            ["retry_of_task_id"],
        )
        batch_op.create_index(batch_op.f("ix_analysis_tasks_status"), ["status"])


def downgrade() -> None:
    with op.batch_alter_table("analysis_tasks") as batch_op:
        batch_op.drop_index(batch_op.f("ix_analysis_tasks_status"))
        batch_op.drop_index(batch_op.f("ix_analysis_tasks_retry_of_task_id"))
    op.drop_table("analysis_tasks")
