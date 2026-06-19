from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "027f97ab3db2"
METADATA_REVISION = "8bcdd86d27ba"


def test_metadata_migration_preserves_source_url_and_supports_downgrade(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"metadata-migration-{uuid4().hex}.db"
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
                    INSERT INTO media (
                        title,
                        alternative_titles,
                        media_type,
                        source_url
                    )
                    VALUES (
                        :title,
                        :alternative_titles,
                        :media_type,
                        :source_url
                    )
                    """
                ),
                {
                    "title": "Existing movie",
                    "alternative_titles": "[]",
                    "media_type": "MOVIE",
                    "source_url": "https://example.com/existing",
                },
            )
        engine.dispose()

        command.upgrade(config, METADATA_REVISION)
        engine = create_engine(database_url)
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("media")}
        indexes = {index["name"] for index in inspector.get_indexes("media")}
        checks = {constraint["name"] for constraint in inspector.get_check_constraints("media")}
        with engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                        source_page_url,
                        status,
                        directors,
                        actors,
                        regions,
                        languages,
                        genres
                    FROM media
                    """
                )
            ).one()
            connection.execute(
                text(
                    """
                    UPDATE media
                    SET media_type = 'DOCUMENTARY'
                    """
                )
            )

        assert "source_url" not in columns
        assert "source_page_url" in columns
        assert row.source_page_url == "https://example.com/existing"
        assert row.status == "PENDING"
        assert row.directors == "[]"
        assert row.actors == "[]"
        assert row.regions == "[]"
        assert row.languages == "[]"
        assert row.genres == "[]"
        assert {"ix_media_status", "ix_media_source_site"} <= indexes
        assert {
            "ck_media_duration_positive",
            "ck_media_rating_range",
        } <= checks
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        downgraded_columns = {column["name"] for column in inspect(engine).get_columns("media")}
        with engine.connect() as connection:
            downgraded = connection.execute(text("SELECT source_url, media_type FROM media")).one()

        assert "source_page_url" not in downgraded_columns
        assert downgraded.source_url == "https://example.com/existing"
        assert downgraded.media_type == "OTHER"
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
