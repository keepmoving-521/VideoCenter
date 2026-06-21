"""Add media directory configuration.

Revision ID: 79c5840db912
Revises: ec06ac928b64
Create Date: 2026-06-21 04:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "79c5840db912"
down_revision: str | Sequence[str] | None = "ec06ac928b64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_directories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("path", sa.String(length=2048), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("auto_scan", sa.Boolean(), server_default="1", nullable=False),
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
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("path"),
    )
    with op.batch_alter_table("media_directories") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_media_directories_is_default"),
            ["is_default"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_media_directories_is_enabled"),
            ["is_enabled"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_media_directories_name"),
            ["name"],
            unique=True,
        )
        batch_op.create_index(
            batch_op.f("ix_media_directories_path"),
            ["path"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("media_directories") as batch_op:
        batch_op.drop_index(batch_op.f("ix_media_directories_path"))
        batch_op.drop_index(batch_op.f("ix_media_directories_name"))
        batch_op.drop_index(batch_op.f("ix_media_directories_is_enabled"))
        batch_op.drop_index(batch_op.f("ix_media_directories_is_default"))
    op.drop_table("media_directories")
