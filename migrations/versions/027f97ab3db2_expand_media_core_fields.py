"""Add core descriptive fields to media records.

Revision ID: 027f97ab3db2
Revises: 81fd73d3a90a
Create Date: 2026-06-20 06:12:14.877438

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "027f97ab3db2"
down_revision: str | Sequence[str] | None = "81fd73d3a90a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add sortable and release metadata while preserving existing rows."""
    with op.batch_alter_table("media", schema=None) as batch_op:
        batch_op.add_column(sa.Column("sort_title", sa.String(length=255), nullable=True))
        batch_op.add_column(
            sa.Column(
                "alternative_titles",
                sa.JSON(),
                server_default="[]",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("release_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("content_rating", sa.String(length=32), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_media_sort_title"),
            ["sort_title"],
            unique=False,
        )


def downgrade() -> None:
    """Remove the core descriptive fields added by this revision."""
    with op.batch_alter_table("media", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_media_sort_title"))
        batch_op.drop_column("content_rating")
        batch_op.drop_column("release_date")
        batch_op.drop_column("alternative_titles")
        batch_op.drop_column("sort_title")
