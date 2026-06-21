"""Add local resource availability and scan difference counters.

Revision ID: f809bb912daf
Revises: e191f7270b02
Create Date: 2026-06-21 05:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f809bb912daf"
down_revision: str | Sequence[str] | None = "e191f7270b02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("local_resources") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_available",
                sa.Boolean(),
                server_default="1",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("missing_at", sa.DateTime(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_local_resources_is_available"),
            ["is_available"],
            unique=False,
        )

    with op.batch_alter_table("scan_tasks") as batch_op:
        batch_op.add_column(
            sa.Column(
                "missing_files",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(
            sa.Column(
                "restored_files",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("scan_tasks") as batch_op:
        batch_op.drop_column("restored_files")
        batch_op.drop_column("missing_files")
    with op.batch_alter_table("local_resources") as batch_op:
        batch_op.drop_index(batch_op.f("ix_local_resources_is_available"))
        batch_op.drop_column("missing_at")
        batch_op.drop_column("is_available")
