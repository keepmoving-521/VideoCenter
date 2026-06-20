"""Add media personal preferences.

Revision ID: 2e9d613cec84
Revises: 3e5fa1d03c30
Create Date: 2026-06-20 07:55:07.891870

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "2e9d613cec84"
down_revision: str | Sequence[str] | None = "3e5fa1d03c30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("media") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_favorite",
                sa.Boolean(),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("personal_rating", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("personal_notes", sa.Text(), nullable=True))
        batch_op.create_check_constraint(
            "ck_media_personal_rating_range",
            "personal_rating IS NULL OR (personal_rating >= 0 AND personal_rating <= 10)",
        )
        batch_op.create_index(
            batch_op.f("ix_media_is_favorite"),
            ["is_favorite"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("media") as batch_op:
        batch_op.drop_index(batch_op.f("ix_media_is_favorite"))
        batch_op.drop_constraint(
            "ck_media_personal_rating_range",
            type_="check",
        )
        batch_op.drop_column("personal_notes")
        batch_op.drop_column("personal_rating")
        batch_op.drop_column("is_favorite")
