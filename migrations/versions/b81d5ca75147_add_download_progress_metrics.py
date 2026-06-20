"""Add download progress, speed, and remaining time metrics.

Revision ID: b81d5ca75147
Revises: 6f17a72c8e41
Create Date: 2026-06-21 00:20:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b81d5ca75147"
down_revision: str | Sequence[str] | None = "6f17a72c8e41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("download_tasks") as batch_op:
        batch_op.add_column(
            sa.Column(
                "downloaded_bytes",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("total_bytes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("speed_bytes_per_second", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("remaining_seconds", sa.Float(), nullable=True))
        batch_op.create_check_constraint(
            "ck_download_progress_range",
            "progress >= 0 AND progress <= 100",
        )
        batch_op.create_check_constraint(
            "ck_download_downloaded_bytes_non_negative",
            "downloaded_bytes >= 0",
        )
        batch_op.create_check_constraint(
            "ck_download_total_bytes_positive",
            "total_bytes IS NULL OR total_bytes > 0",
        )
        batch_op.create_check_constraint(
            "ck_download_speed_non_negative",
            "speed_bytes_per_second IS NULL OR speed_bytes_per_second >= 0",
        )
        batch_op.create_check_constraint(
            "ck_download_remaining_seconds_non_negative",
            "remaining_seconds IS NULL OR remaining_seconds >= 0",
        )

    op.execute(
        """
        UPDATE download_tasks
        SET downloaded_bytes = CASE
            WHEN status = 'COMPLETED' THEN COALESCE(
                (
                    SELECT file_size
                    FROM local_resources
                    WHERE local_resources.file_path = download_tasks.target_path
                    ORDER BY local_resources.id DESC
                    LIMIT 1
                ),
                0
            )
            ELSE 0
        END
        """
    )
    op.execute(
        """
        UPDATE download_tasks
        SET total_bytes = downloaded_bytes,
            remaining_seconds = 0
        WHERE status = 'COMPLETED' AND downloaded_bytes > 0
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("download_tasks") as batch_op:
        batch_op.drop_constraint(
            "ck_download_remaining_seconds_non_negative",
            type_="check",
        )
        batch_op.drop_constraint("ck_download_speed_non_negative", type_="check")
        batch_op.drop_constraint("ck_download_total_bytes_positive", type_="check")
        batch_op.drop_constraint(
            "ck_download_downloaded_bytes_non_negative",
            type_="check",
        )
        batch_op.drop_constraint("ck_download_progress_range", type_="check")
        batch_op.drop_column("remaining_seconds")
        batch_op.drop_column("speed_bytes_per_second")
        batch_op.drop_column("total_bytes")
        batch_op.drop_column("downloaded_bytes")
