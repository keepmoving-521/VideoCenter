"""Add generated video cover and preview thumbnails.

Revision ID: c8f42e6d1a90
Revises: b57e1984c2ad
Create Date: 2026-06-21 16:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8f42e6d1a90"
down_revision: str | Sequence[str] | None = "b57e1984c2ad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("local_resources") as batch_op:
        batch_op.add_column(sa.Column("cover_image_path", sa.String(2048), nullable=True))
        batch_op.add_column(
            sa.Column(
                "preview_thumbnail_paths",
                sa.JSON(),
                server_default="[]",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("visual_assets_generated", sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("local_resources") as batch_op:
        batch_op.drop_column("visual_assets_generated")
        batch_op.drop_column("preview_thumbnail_paths")
        batch_op.drop_column("cover_image_path")
