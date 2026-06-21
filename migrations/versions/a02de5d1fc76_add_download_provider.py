"""Add download provider selection.

Revision ID: a02de5d1fc76
Revises: 8651d026e704
Create Date: 2026-06-21 02:45:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a02de5d1fc76"
down_revision: str | Sequence[str] | None = "8651d026e704"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("download_tasks") as batch_op:
        batch_op.add_column(
            sa.Column(
                "downloader_name",
                sa.String(length=50),
                server_default="auto",
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("download_tasks") as batch_op:
        batch_op.drop_column("downloader_name")
