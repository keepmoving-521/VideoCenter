"""Add media artwork, tags, seasons, and episodes.

Revision ID: 3e5fa1d03c30
Revises: 8bcdd86d27ba
Create Date: 2026-06-20 06:52:36.637801

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3e5fa1d03c30"
down_revision: str | Sequence[str] | None = "8bcdd86d27ba"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("normalized_name", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("tags") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_tags_normalized_name"),
            ["normalized_name"],
            unique=True,
        )

    op.create_table(
        "media_tags",
        sa.Column("media_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("media_id", "tag_id"),
    )
    op.create_table(
        "seasons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=False),
        sa.Column("season_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("poster_url", sa.String(length=2048), nullable=True),
        sa.Column("air_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "season_number >= 0",
            name="ck_season_number_non_negative",
        ),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "media_id",
            "season_number",
            name="uq_season_media_number",
        ),
    )
    with op.batch_alter_table("seasons") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_seasons_media_id"),
            ["media_id"],
            unique=False,
        )

    op.create_table(
        "episodes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("season_id", sa.Integer(), nullable=False),
        sa.Column("episode_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("air_date", sa.Date(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=2048), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes > 0",
            name="ck_episode_duration_positive",
        ),
        sa.CheckConstraint(
            "episode_number > 0",
            name="ck_episode_number_positive",
        ),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "season_id",
            "episode_number",
            name="uq_episode_season_number",
        ),
    )
    with op.batch_alter_table("episodes") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_episodes_season_id"),
            ["season_id"],
            unique=False,
        )

    with op.batch_alter_table("media") as batch_op:
        batch_op.add_column(sa.Column("background_url", sa.String(length=2048), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("media") as batch_op:
        batch_op.drop_column("background_url")

    with op.batch_alter_table("episodes") as batch_op:
        batch_op.drop_index(batch_op.f("ix_episodes_season_id"))

    op.drop_table("episodes")
    with op.batch_alter_table("seasons") as batch_op:
        batch_op.drop_index(batch_op.f("ix_seasons_media_id"))

    op.drop_table("seasons")
    op.drop_table("media_tags")
    with op.batch_alter_table("tags") as batch_op:
        batch_op.drop_index(batch_op.f("ix_tags_normalized_name"))

    op.drop_table("tags")
