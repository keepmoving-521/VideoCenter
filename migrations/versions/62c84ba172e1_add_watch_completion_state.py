"""Add watch completion state.

Revision ID: 62c84ba172e1
Revises: e73b4a90c251
Create Date: 2026-06-21 21:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "62c84ba172e1"
down_revision: str | Sequence[str] | None = "e73b4a90c251"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("watch_history") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_completed",
                sa.Boolean(),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_watch_history_is_completed"),
            ["is_completed"],
            unique=False,
        )

    op.execute(
        sa.text(
            """
            UPDATE watch_history
            SET is_completed = 1,
                completed_at = watched_at
            WHERE duration_seconds IS NOT NULL
              AND duration_seconds > 0
              AND position_seconds / duration_seconds >= 0.95
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("watch_history") as batch_op:
        batch_op.drop_index(batch_op.f("ix_watch_history_is_completed"))
        batch_op.drop_column("completed_at")
        batch_op.drop_column("is_completed")
