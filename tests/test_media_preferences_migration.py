from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "3e5fa1d03c30"
PREFERENCES_REVISION = "2e9d613cec84"


def test_media_preferences_migration_preserves_existing_records(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"preferences-migration-{uuid4().hex}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config(project_root / "alembic.ini")

    monkeypatch.setenv("VIDEOCENTER_DATABASE_URL", database_url)
    get_settings.cache_clear()
    engine = None

    try:
        command.upgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO media (title, alternative_titles, media_type)
                    VALUES ('Existing movie', '[]', 'MOVIE')
                    """
                )
            )
        engine.dispose()
        engine = None

        command.upgrade(config, PREFERENCES_REVISION)
        engine = create_engine(database_url)
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("media")}
        indexes = {index["name"] for index in inspector.get_indexes("media")}
        checks = {constraint["name"] for constraint in inspector.get_check_constraints("media")}
        with engine.begin() as connection:
            existing = connection.execute(
                text(
                    """
                    SELECT is_favorite, personal_rating, personal_notes
                    FROM media
                    """
                )
            ).one()
            connection.execute(
                text(
                    """
                    UPDATE media
                    SET is_favorite = 1,
                        personal_rating = 9.5,
                        personal_notes = 'Favorite'
                    """
                )
            )

        assert {"is_favorite", "personal_rating", "personal_notes"} <= columns
        assert "ix_media_is_favorite" in indexes
        assert "ck_media_personal_rating_range" in checks
        assert existing.is_favorite == 0
        assert existing.personal_rating is None
        assert existing.personal_notes is None
        engine.dispose()
        engine = None

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        downgraded_columns = {column["name"] for column in inspect(engine).get_columns("media")}
        assert (
            not {
                "is_favorite",
                "personal_rating",
                "personal_notes",
            }
            & downgraded_columns
        )
    finally:
        if engine is not None:
            engine.dispose()
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
