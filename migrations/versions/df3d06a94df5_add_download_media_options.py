"""Add download quality, format, subtitle, and thumbnail options.

Revision ID: df3d06a94df5
Revises: a02de5d1fc76
Create Date: 2026-06-21 03:15:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "df3d06a94df5"
down_revision: str | Sequence[str] | None = "a02de5d1fc76"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("download_tasks") as batch_op:
        batch_op.add_column(
            sa.Column(
                "video_quality",
                sa.String(length=20),
                server_default="best",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "video_format",
                sa.String(length=20),
                server_default="best",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "download_subtitles",
                sa.Boolean(),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "subtitle_languages",
                sa.JSON(),
                server_default="[]",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "download_thumbnail",
                sa.Boolean(),
                server_default="0",
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("download_tasks") as batch_op:
        batch_op.drop_column("download_thumbnail")
        batch_op.drop_column("subtitle_languages")
        batch_op.drop_column("download_subtitles")
        batch_op.drop_column("video_format")
        batch_op.drop_column("video_quality")
