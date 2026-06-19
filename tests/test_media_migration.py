from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from videocenter.core.config import get_settings

INITIAL_REVISION = "81fd73d3a90a"
M01_REVISION = "027f97ab3db2"


def test_m01_migration_preserves_existing_media_rows(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"m01-migration-{uuid4().hex}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config(project_root / "alembic.ini")

    monkeypatch.setenv("VIDEOCENTER_DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        command.upgrade(config, INITIAL_REVISION)
        engine = create_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO media (title, media_type)
                    VALUES (:title, :media_type)
                    """
                ),
                {"title": "Existing movie", "media_type": "MOVIE"},
            )
        engine.dispose()

        command.upgrade(config, M01_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("media")}
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT title, alternative_titles
                    FROM media
                    """
                )
            ).one()

        assert {
            "sort_title",
            "alternative_titles",
            "release_date",
            "content_rating",
        } <= columns
        assert row.title == "Existing movie"
        assert row.alternative_titles == "[]"
        engine.dispose()

        command.downgrade(config, INITIAL_REVISION)
        engine = create_engine(database_url)
        downgraded_columns = {column["name"] for column in inspect(engine).get_columns("media")}
        assert "alternative_titles" not in downgraded_columns
        assert "sort_title" not in downgraded_columns
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
