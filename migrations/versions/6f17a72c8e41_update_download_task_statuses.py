"""Update download task statuses for queue processing.

Revision ID: 6f17a72c8e41
Revises: 2e9d613cec84
Create Date: 2026-06-20 23:58:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6f17a72c8e41"
down_revision: str | Sequence[str] | None = "2e9d613cec84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

old_status = sa.Enum(
    "PENDING",
    "RUNNING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    name="downloadstatus",
)
new_status = sa.Enum(
    "WAITING",
    "DOWNLOADING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
    name="downloadstatus",
)


def upgrade() -> None:
    op.execute("UPDATE download_tasks SET status = 'WAITING' WHERE status = 'PENDING'")
    op.execute("UPDATE download_tasks SET status = 'DOWNLOADING' WHERE status = 'RUNNING'")
    with op.batch_alter_table("download_tasks") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=old_status,
            type_=new_status,
            existing_nullable=False,
        )


def downgrade() -> None:
    op.execute("UPDATE download_tasks SET status = 'PENDING' WHERE status = 'WAITING'")
    op.execute("UPDATE download_tasks SET status = 'RUNNING' WHERE status = 'DOWNLOADING'")
    with op.batch_alter_table("download_tasks") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=new_status,
            type_=old_status,
            existing_nullable=False,
        )
