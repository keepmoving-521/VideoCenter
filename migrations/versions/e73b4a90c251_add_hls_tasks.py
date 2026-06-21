"""Add HLS transcoding tasks.

Revision ID: e73b4a90c251
Revises: d91a7f2e4b63
Create Date: 2026-06-21 18:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e73b4a90c251"
down_revision: str | Sequence[str] | None = "d91a7f2e4b63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hls_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "WAITING",
                "RUNNING",
                "COMPLETED",
                "FAILED",
                name="hlstaskstatus",
            ),
            nullable=False,
        ),
        sa.Column("progress", sa.Float(), server_default="0", nullable=False),
        sa.Column("output_directory", sa.String(2048), nullable=True),
        sa.Column("playlist_path", sa.String(2048), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["local_resources.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("hls_tasks") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_hls_tasks_resource_id"),
            ["resource_id"],
        )
        batch_op.create_index(batch_op.f("ix_hls_tasks_status"), ["status"])


def downgrade() -> None:
    with op.batch_alter_table("hls_tasks") as batch_op:
        batch_op.drop_index(batch_op.f("ix_hls_tasks_status"))
        batch_op.drop_index(batch_op.f("ix_hls_tasks_resource_id"))
    op.drop_table("hls_tasks")
