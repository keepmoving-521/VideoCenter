from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "8651d026e704"
PROVIDER_REVISION = "a02de5d1fc76"


def test_download_provider_migration_adds_default(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"download-provider-{uuid4().hex}.db"
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
                        target_directory,
                        status,
                        priority,
                        progress,
                        downloaded_bytes
                    )
                    VALUES (
                        'https://example.com/video.mp4',
                        'video.mp4',
                        '',
                        'WAITING',
                        0,
                        0,
                        0
                    )
                    """
                )
            )
        engine.dispose()

        command.upgrade(config, PROVIDER_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("download_tasks")}
        with engine.connect() as connection:
            provider = connection.execute(
                text("SELECT downloader_name FROM download_tasks")
            ).scalar_one()
        assert "downloader_name" in columns
        assert provider == "auto"
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("download_tasks")}
        assert "downloader_name" not in columns
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
