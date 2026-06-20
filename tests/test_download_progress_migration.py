from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "6f17a72c8e41"
PROGRESS_REVISION = "b81d5ca75147"


def test_download_progress_migration_adds_metrics_and_preserves_tasks(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"download-progress-{uuid4().hex}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config(project_root / "alembic.ini")

    monkeypatch.setenv("VIDEOCENTER_DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        command.upgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO download_tasks (
                        source_url,
                        target_name,
                        status,
                        progress
                    )
                    VALUES (
                        'https://example.com/video.mp4',
                        'video.mp4',
                        'WAITING',
                        0
                    )
                    """
                )
            )
        engine.dispose()

        command.upgrade(config, PROGRESS_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("download_tasks")}
        checks = {
            constraint["name"]
            for constraint in inspect(engine).get_check_constraints("download_tasks")
        }
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                        downloaded_bytes,
                        total_bytes,
                        speed_bytes_per_second,
                        remaining_seconds
                    FROM download_tasks
                    """
                )
            ).one()

        assert {
            "downloaded_bytes",
            "total_bytes",
            "speed_bytes_per_second",
            "remaining_seconds",
        } <= columns
        assert {
            "ck_download_progress_range",
            "ck_download_downloaded_bytes_non_negative",
            "ck_download_total_bytes_positive",
            "ck_download_speed_non_negative",
            "ck_download_remaining_seconds_non_negative",
        } <= checks
        assert row.downloaded_bytes == 0
        assert row.total_bytes is None
        assert row.speed_bytes_per_second is None
        assert row.remaining_seconds is None
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        downgraded_columns = {
            column["name"] for column in inspect(engine).get_columns("download_tasks")
        }
        assert "downloaded_bytes" not in downgraded_columns
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
