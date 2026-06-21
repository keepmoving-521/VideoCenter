from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "a06f2c31d984"
STREAM_REVISION = "b57e1984c2ad"
STREAM_COLUMNS = {"audio_codec", "audio_tracks", "embedded_subtitles"}


def test_audio_subtitle_stream_migration_adds_defaults_and_reprobe_flag(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"stream-info-{uuid4().hex}.db"
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
                    INSERT INTO local_resources (
                        file_path, file_name, file_size, mime_type,
                        media_info_probed
                    )
                    VALUES (
                        'C:/media/movie.mkv', 'movie.mkv', 100,
                        'video/x-matroska', 1
                    )
                    """
                )
            )
        engine.dispose()

        command.upgrade(config, STREAM_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("local_resources")}
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT audio_codec, audio_tracks, embedded_subtitles,
                           media_info_probed
                    FROM local_resources
                    """
                )
            ).one()
        assert STREAM_COLUMNS <= columns
        assert row.audio_codec is None
        assert row.audio_tracks == "[]"
        assert row.embedded_subtitles == "[]"
        assert row.media_info_probed == 0
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("local_resources")}
        assert STREAM_COLUMNS.isdisjoint(columns)
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
