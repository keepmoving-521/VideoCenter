"""Add background scan tasks and incremental resource metadata.

Revision ID: e191f7270b02
Revises: 79c5840db912
Create Date: 2026-06-21 05:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e191f7270b02"
down_revision: str | Sequence[str] | None = "79c5840db912"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("local_resources") as batch_op:
        batch_op.add_column(sa.Column("modified_at_ns", sa.Integer(), nullable=True))

    op.create_table(
        "scan_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(length=2048), nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=True),
        sa.Column("incremental", sa.Boolean(), server_default="1", nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "WAITING",
                "RUNNING",
                "COMPLETED",
                "FAILED",
                name="scantaskstatus",
            ),
            nullable=False,
        ),
        sa.Column("progress", sa.Float(), server_default="0", nullable=False),
        sa.Column("total_files", sa.Integer(), server_default="0", nullable=False),
        sa.Column("processed_files", sa.Integer(), server_default="0", nullable=False),
        sa.Column("discovered_files", sa.Integer(), server_default="0", nullable=False),
        sa.Column("added_files", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_files", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skipped_files", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("scan_tasks") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_scan_tasks_media_id"),
            ["media_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_scan_tasks_status"),
            ["status"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("scan_tasks") as batch_op:
        batch_op.drop_index(batch_op.f("ix_scan_tasks_status"))
        batch_op.drop_index(batch_op.f("ix_scan_tasks_media_id"))
    op.drop_table("scan_tasks")
    with op.batch_alter_table("local_resources") as batch_op:
        batch_op.drop_column("modified_at_ns")
