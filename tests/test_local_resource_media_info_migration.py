from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "f20a6b183e74"
MEDIA_INFO_REVISION = "a06f2c31d984"
MEDIA_INFO_COLUMNS = {
    "video_width",
    "video_height",
    "video_codec",
    "bitrate",
    "media_info_probed",
}


def test_local_resource_media_info_migration_adds_fields_and_default(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"media-info-{uuid4().hex}.db"
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
                        file_path, file_name, file_size, mime_type
                    )
                    VALUES ('C:/media/movie.mp4', 'movie.mp4', 100, 'video/mp4')
                    """
                )
            )
        engine.dispose()

        command.upgrade(config, MEDIA_INFO_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("local_resources")}
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT video_width, video_height, video_codec,
                           bitrate, media_info_probed
                    FROM local_resources
                    """
                )
            ).one()
        assert MEDIA_INFO_COLUMNS <= columns
        assert row.video_width is None
        assert row.video_height is None
        assert row.video_codec is None
        assert row.bitrate is None
        assert row.media_info_probed == 0
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("local_resources")}
        assert MEDIA_INFO_COLUMNS.isdisjoint(columns)
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
