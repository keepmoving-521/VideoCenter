"""Add probed video media information.

Revision ID: a06f2c31d984
Revises: f20a6b183e74
Create Date: 2026-06-21 14:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a06f2c31d984"
down_revision: str | Sequence[str] | None = "f20a6b183e74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("local_resources") as batch_op:
        batch_op.add_column(sa.Column("video_width", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("video_height", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("video_codec", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("bitrate", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "media_info_probed",
                sa.Boolean(),
                server_default="0",
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("local_resources") as batch_op:
        batch_op.drop_column("media_info_probed")
        batch_op.drop_column("bitrate")
        batch_op.drop_column("video_codec")
        batch_op.drop_column("video_height")
        batch_op.drop_column("video_width")
