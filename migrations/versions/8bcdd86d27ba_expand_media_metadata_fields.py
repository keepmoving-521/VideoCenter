"""Expand media lifecycle, source and descriptive metadata.

Revision ID: 8bcdd86d27ba
Revises: 027f97ab3db2
Create Date: 2026-06-20 06:33:47.798845

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8bcdd86d27ba"
down_revision: str | Sequence[str] | None = "027f97ab3db2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_MEDIA_TYPE = sa.Enum("MOVIE", "SERIES", "OTHER", name="mediatype")
NEW_MEDIA_TYPE = sa.Enum(
    "MOVIE",
    "SERIES",
    "DOCUMENTARY",
    "ANIMATION",
    "VARIETY_SHOW",
    "SHORT_FILM",
    "OTHER",
    name="mediatype",
)


def upgrade() -> None:
    """Add M02-M08 fields without losing existing source page URLs."""
    with op.batch_alter_table("media", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                sa.Enum(
                    "PENDING",
                    "DOWNLOADING",
                    "AVAILABLE",
                    "MISSING",
                    "ARCHIVED",
                    name="mediastatus",
                ),
                server_default="PENDING",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("source_site", sa.String(length=100), nullable=True))
        batch_op.alter_column(
            "source_url",
            new_column_name="source_page_url",
            existing_type=sa.String(length=2048),
            existing_nullable=True,
        )
        for column_name in ("directors", "actors", "regions", "languages", "genres"):
            batch_op.add_column(
                sa.Column(
                    column_name,
                    sa.JSON(),
                    server_default="[]",
                    nullable=False,
                )
            )
        batch_op.add_column(sa.Column("duration_minutes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("rating", sa.Float(), nullable=True))
        batch_op.alter_column(
            "media_type",
            existing_type=OLD_MEDIA_TYPE,
            type_=NEW_MEDIA_TYPE,
            existing_nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_media_duration_positive",
            "duration_minutes IS NULL OR duration_minutes > 0",
        )
        batch_op.create_check_constraint(
            "ck_media_rating_range",
            "rating IS NULL OR (rating >= 0 AND rating <= 10)",
        )
        batch_op.create_index(
            batch_op.f("ix_media_source_site"),
            ["source_site"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_media_status"),
            ["status"],
            unique=False,
        )


def downgrade() -> None:
    """Remove M02-M08 fields while preserving the original source URL."""
    op.execute(
        """
        UPDATE media
        SET media_type = 'OTHER'
        WHERE media_type NOT IN ('MOVIE', 'SERIES', 'OTHER')
        """
    )

    with op.batch_alter_table("media", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_media_status"))
        batch_op.drop_index(batch_op.f("ix_media_source_site"))
        batch_op.drop_constraint("ck_media_rating_range", type_="check")
        batch_op.drop_constraint("ck_media_duration_positive", type_="check")
        batch_op.alter_column(
            "media_type",
            existing_type=NEW_MEDIA_TYPE,
            type_=OLD_MEDIA_TYPE,
            existing_nullable=False,
        )
        batch_op.drop_column("rating")
        batch_op.drop_column("duration_minutes")
        for column_name in ("genres", "languages", "regions", "actors", "directors"):
            batch_op.drop_column(column_name)
        batch_op.alter_column(
            "source_page_url",
            new_column_name="source_url",
            existing_type=sa.String(length=2048),
            existing_nullable=True,
        )
        batch_op.drop_column("source_site")
        batch_op.drop_column("status")
