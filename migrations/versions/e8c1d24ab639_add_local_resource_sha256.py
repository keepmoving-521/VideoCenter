"""Add SHA-256 checksum to local resources.

Revision ID: e8c1d24ab639
Revises: c35a942f71de
Create Date: 2026-06-21 10:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8c1d24ab639"
down_revision: str | Sequence[str] | None = "c35a942f71de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("local_resources") as batch_op:
        batch_op.add_column(sa.Column("checksum_sha256", sa.String(64), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_local_resources_checksum_sha256"),
            ["checksum_sha256"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("local_resources") as batch_op:
        batch_op.drop_index(batch_op.f("ix_local_resources_checksum_sha256"))
        batch_op.drop_column("checksum_sha256")
