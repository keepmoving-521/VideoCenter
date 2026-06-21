"""Add recent watched episode to watch history.

Revision ID: 341af49d67c8
Revises: 62c84ba172e1
Create Date: 2026-06-21 23:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "341af49d67c8"
down_revision: str | Sequence[str] | None = "62c84ba172e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("watch_history") as batch_op:
        batch_op.add_column(sa.Column("episode_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_watch_history_episode_id_episodes",
            "episodes",
            ["episode_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            batch_op.f("ix_watch_history_episode_id"),
            ["episode_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("watch_history") as batch_op:
        batch_op.drop_index(batch_op.f("ix_watch_history_episode_id"))
        batch_op.drop_constraint(
            "fk_watch_history_episode_id_episodes",
            type_="foreignkey",
        )
        batch_op.drop_column("episode_id")
