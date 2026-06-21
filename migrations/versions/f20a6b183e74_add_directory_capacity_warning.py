"""Add media directory capacity warning settings.

Revision ID: f20a6b183e74
Revises: e8c1d24ab639
Create Date: 2026-06-21 12:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f20a6b183e74"
down_revision: str | Sequence[str] | None = "e8c1d24ab639"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("media_directories") as batch_op:
        batch_op.add_column(
            sa.Column(
                "capacity_warning_enabled",
                sa.Boolean(),
                server_default="1",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "capacity_warning_threshold_percent",
                sa.Integer(),
                server_default="90",
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "ck_media_directory_capacity_warning_threshold",
            "capacity_warning_threshold_percent >= 1 AND capacity_warning_threshold_percent <= 100",
        )


def downgrade() -> None:
    with op.batch_alter_table("media_directories") as batch_op:
        batch_op.drop_constraint(
            "ck_media_directory_capacity_warning_threshold",
            type_="check",
        )
        batch_op.drop_column("capacity_warning_threshold_percent")
        batch_op.drop_column("capacity_warning_enabled")
