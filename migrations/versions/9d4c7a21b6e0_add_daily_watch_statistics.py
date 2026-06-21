"""Add daily watch statistics.

Revision ID: 9d4c7a21b6e0
Revises: 341af49d67c8
Create Date: 2026-06-22 00:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9d4c7a21b6e0"
down_revision: str | Sequence[str] | None = "341af49d67c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "watch_daily_stats",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stat_date", sa.Date(), nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=False),
        sa.Column(
            "watched_seconds",
            sa.Float(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "completion_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["media_id"],
            ["media.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "stat_date",
            "media_id",
            name="uq_watch_daily_date_media",
        ),
    )
    with op.batch_alter_table("watch_daily_stats") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_watch_daily_stats_media_id"),
            ["media_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_watch_daily_stats_stat_date"),
            ["stat_date"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("watch_daily_stats") as batch_op:
        batch_op.drop_index(batch_op.f("ix_watch_daily_stats_stat_date"))
        batch_op.drop_index(batch_op.f("ix_watch_daily_stats_media_id"))
    op.drop_table("watch_daily_stats")
