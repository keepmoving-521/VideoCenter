from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "a02de5d1fc76"
OPTIONS_REVISION = "df3d06a94df5"


def test_download_media_options_migration_adds_defaults(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"download-options-{uuid4().hex}.db"
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
                        downloader_name,
                        status,
                        priority,
                        progress,
                        downloaded_bytes
                    )
                    VALUES (
                        'https://example.com/video.mp4',
                        'video.mp4',
                        '',
                        'http-direct',
                        'WAITING',
                        0,
                        0,
                        0
                    )
                    """
                )
            )
        engine.dispose()

        command.upgrade(config, OPTIONS_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("download_tasks")}
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                        video_quality,
                        video_format,
                        download_subtitles,
                        subtitle_languages,
                        download_thumbnail
                    FROM download_tasks
                    """
                )
            ).one()

        assert {
            "video_quality",
            "video_format",
            "download_subtitles",
            "subtitle_languages",
            "download_thumbnail",
        } <= columns
        assert row.video_quality == "best"
        assert row.video_format == "best"
        assert row.download_subtitles == 0
        assert row.subtitle_languages == "[]"
        assert row.download_thumbnail == 0
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("download_tasks")}
        assert "video_quality" not in columns
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
