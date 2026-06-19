"""Create the initial VideoCenter database schema.

Revision ID: 81fd73d3a90a
Revises:
Create Date: 2026-06-19 18:53:40.888284

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "81fd73d3a90a"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all initial application tables."""
    op.create_table(
        "media",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("original_title", sa.String(length=255), nullable=True),
        sa.Column(
            "media_type",
            sa.Enum("MOVIE", "SERIES", "OTHER", name="mediatype"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("release_year", sa.Integer(), nullable=True),
        sa.Column("poster_url", sa.String(length=2048), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("media", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_media_media_type"), ["media_type"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_media_title"), ["title"], unique=False)

    op.create_table(
        "download_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("target_name", sa.String(length=512), nullable=False),
        sa.Column("target_path", sa.String(length=2048), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "RUNNING",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                name="downloadstatus",
            ),
            nullable=False,
        ),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["media_id"], ["media.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("download_tasks", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_download_tasks_media_id"), ["media_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_download_tasks_status"), ["status"], unique=False
        )

    op.create_table(
        "local_resources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=True),
        sa.Column("file_path", sa.String(length=2048), nullable=False),
        sa.Column("file_name", sa.String(length=512), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_path"),
    )
    with op.batch_alter_table("local_resources", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_local_resources_media_id"), ["media_id"], unique=False
        )

    op.create_table(
        "watch_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("media_id", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("position_seconds", sa.Float(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column(
            "watched_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"]),
        sa.ForeignKeyConstraint(["resource_id"], ["local_resources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("media_id", name="uq_history_media"),
    )
    with op.batch_alter_table("watch_history", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_watch_history_media_id"), ["media_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_watch_history_watched_at"), ["watched_at"], unique=False
        )


def downgrade() -> None:
    """Remove all initial application tables."""
    with op.batch_alter_table("watch_history", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_watch_history_watched_at"))
        batch_op.drop_index(batch_op.f("ix_watch_history_media_id"))

    op.drop_table("watch_history")
    with op.batch_alter_table("local_resources", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_local_resources_media_id"))

    op.drop_table("local_resources")
    with op.batch_alter_table("download_tasks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_download_tasks_status"))
        batch_op.drop_index(batch_op.f("ix_download_tasks_media_id"))

    op.drop_table("download_tasks")
    with op.batch_alter_table("media", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_media_title"))
        batch_op.drop_index(batch_op.f("ix_media_media_type"))

    op.drop_table("media")
