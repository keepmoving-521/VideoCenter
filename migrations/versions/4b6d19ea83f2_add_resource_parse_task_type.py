"""Add resource parse background task type.

Revision ID: 4b6d19ea83f2
Revises: 73e2b8f940a1
Create Date: 2026-06-22 02:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4b6d19ea83f2"
down_revision: str | Sequence[str] | None = "73e2b8f940a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_TASK_TYPE = sa.Enum(
    "DOWNLOAD",
    "MEDIA_SCAN",
    "MEDIA_ANALYSIS",
    "HLS_TRANSCODE",
    "GENERIC",
    name="backgroundtasktype",
)
NEW_TASK_TYPE = sa.Enum(
    "RESOURCE_PARSE",
    "DOWNLOAD",
    "MEDIA_SCAN",
    "MEDIA_ANALYSIS",
    "HLS_TRANSCODE",
    "GENERIC",
    name="backgroundtasktype",
)


def upgrade() -> None:
    with op.batch_alter_table("background_tasks") as batch_op:
        batch_op.alter_column(
            "task_type",
            existing_type=OLD_TASK_TYPE,
            type_=NEW_TASK_TYPE,
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("background_tasks") as batch_op:
        batch_op.alter_column(
            "task_type",
            existing_type=NEW_TASK_TYPE,
            type_=OLD_TASK_TYPE,
            existing_nullable=False,
        )
