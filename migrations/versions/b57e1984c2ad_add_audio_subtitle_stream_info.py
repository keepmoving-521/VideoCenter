"""Add audio tracks and embedded subtitle information.

Revision ID: b57e1984c2ad
Revises: a06f2c31d984
Create Date: 2026-06-21 15:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b57e1984c2ad"
down_revision: str | Sequence[str] | None = "a06f2c31d984"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("local_resources") as batch_op:
        batch_op.add_column(sa.Column("audio_codec", sa.String(100), nullable=True))
        batch_op.add_column(
            sa.Column(
                "audio_tracks",
                sa.JSON(),
                server_default="[]",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "embedded_subtitles",
                sa.JSON(),
                server_default="[]",
                nullable=False,
            )
        )
    op.execute("UPDATE local_resources SET media_info_probed = 0")


def downgrade() -> None:
    with op.batch_alter_table("local_resources") as batch_op:
        batch_op.drop_column("embedded_subtitles")
        batch_op.drop_column("audio_tracks")
        batch_op.drop_column("audio_codec")
