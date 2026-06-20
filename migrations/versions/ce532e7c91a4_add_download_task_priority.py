"""Add download task priority.

Revision ID: ce532e7c91a4
Revises: cf6e704f63c2
Create Date: 2026-06-21 01:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ce532e7c91a4"
down_revision: str | Sequence[str] | None = "cf6e704f63c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("download_tasks") as batch_op:
        batch_op.add_column(sa.Column("priority", sa.Integer(), server_default="0", nullable=False))
        batch_op.create_check_constraint(
            "ck_download_priority_range",
            "priority >= -100 AND priority <= 100",
        )
        batch_op.create_index(
            batch_op.f("ix_download_tasks_priority"),
            ["priority"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("download_tasks") as batch_op:
        batch_op.drop_index(batch_op.f("ix_download_tasks_priority"))
        batch_op.drop_constraint("ck_download_priority_range", type_="check")
        batch_op.drop_column("priority")
