from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "b57e1984c2ad"
ARTWORK_REVISION = "c8f42e6d1a90"
ARTWORK_COLUMNS = {
    "cover_image_path",
    "preview_thumbnail_paths",
    "visual_assets_generated",
}


def test_video_artwork_migration_adds_fields_and_defaults(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"video-artwork-{uuid4().hex}.db"
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

        command.upgrade(config, ARTWORK_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("local_resources")}
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT cover_image_path, preview_thumbnail_paths,
                           visual_assets_generated
                    FROM local_resources
                    """
                )
            ).one()
        assert ARTWORK_COLUMNS <= columns
        assert row.cover_image_path is None
        assert row.preview_thumbnail_paths == "[]"
        assert row.visual_assets_generated is None
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("local_resources")}
        assert ARTWORK_COLUMNS.isdisjoint(columns)
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
