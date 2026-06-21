"""Add local resource filename recognition fields.

Revision ID: c35a942f71de
Revises: f809bb912daf
Create Date: 2026-06-21 08:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c35a942f71de"
down_revision: str | Sequence[str] | None = "f809bb912daf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("local_resources") as batch_op:
        batch_op.add_column(sa.Column("detected_media_type", sa.String(30), nullable=True))
        batch_op.add_column(sa.Column("parsed_title", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("parsed_release_year", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("parsed_season_number", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("parsed_episode_number", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("local_resources") as batch_op:
        batch_op.drop_column("parsed_episode_number")
        batch_op.drop_column("parsed_season_number")
        batch_op.drop_column("parsed_release_year")
        batch_op.drop_column("parsed_title")
        batch_op.drop_column("detected_media_type")
