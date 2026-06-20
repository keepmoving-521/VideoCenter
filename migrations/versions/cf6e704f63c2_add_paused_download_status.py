"""Add paused download task status.

Revision ID: cf6e704f63c2
Revises: b81d5ca75147
Create Date: 2026-06-21 01:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "cf6e704f63c2"
down_revision: str | Sequence[str] | None = "b81d5ca75147"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

old_status = sa.Enum(
    "WAITING",
    "DOWNLOADING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    name="downloadstatus",
)
new_status = sa.Enum(
    "WAITING",
    "DOWNLOADING",
    "PAUSED",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    name="downloadstatus",
)


def upgrade() -> None:
    with op.batch_alter_table("download_tasks") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=old_status,
            type_=new_status,
            existing_nullable=False,
        )


def downgrade() -> None:
    op.execute("UPDATE download_tasks SET status = 'WAITING' WHERE status = 'PAUSED'")
    with op.batch_alter_table("download_tasks") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=new_status,
            type_=old_status,
            existing_nullable=False,
        )
