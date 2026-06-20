"""Add download destination and checksum fields.

Revision ID: 8651d026e704
Revises: ce532e7c91a4
Create Date: 2026-06-21 02:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8651d026e704"
down_revision: str | Sequence[str] | None = "ce532e7c91a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("download_tasks") as batch_op:
        batch_op.add_column(
            sa.Column(
                "target_directory",
                sa.String(length=1024),
                server_default="",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("expected_sha256", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("checksum_sha256", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("download_tasks") as batch_op:
        batch_op.drop_column("checksum_sha256")
        batch_op.drop_column("expected_sha256")
        batch_op.drop_column("target_directory")
