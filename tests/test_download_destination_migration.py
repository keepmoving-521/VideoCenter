from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "ce532e7c91a4"
DESTINATION_REVISION = "8651d026e704"


def test_download_destination_migration_adds_fields_and_defaults(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"download-destination-{uuid4().hex}.db"
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
                        priority,
                        progress,
                        downloaded_bytes
                    )
                    VALUES (
                        'https://example.com/video.mp4',
                        'video.mp4',
                        'WAITING',
                        0,
                        0,
                        0
                    )
                    """
                )
            )
        engine.dispose()

        command.upgrade(config, DESTINATION_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("download_tasks")}
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT target_directory, expected_sha256, checksum_sha256
                    FROM download_tasks
                    """
                )
            ).one()

        assert {
            "target_directory",
            "expected_sha256",
            "checksum_sha256",
        } <= columns
        assert row.target_directory == ""
        assert row.expected_sha256 is None
        assert row.checksum_sha256 is None
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("download_tasks")}
        assert "target_directory" not in columns
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
