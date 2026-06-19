from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "8bcdd86d27ba"
CATALOG_REVISION = "3e5fa1d03c30"


def test_catalog_migration_supports_upgrade_and_downgrade(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"catalog-migration-{uuid4().hex}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config(project_root / "alembic.ini")

    monkeypatch.setenv("VIDEOCENTER_DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        command.upgrade(config, PREVIOUS_REVISION)
        command.upgrade(config, CATALOG_REVISION)

        engine = create_engine(database_url)
        inspector = inspect(engine)
        assert {"tags", "media_tags", "seasons", "episodes"} <= set(inspector.get_table_names())
        assert "background_url" in {column["name"] for column in inspector.get_columns("media")}
        assert {"uq_season_media_number"} <= {
            constraint["name"] for constraint in inspector.get_unique_constraints("seasons")
        }
        assert {"uq_episode_season_number"} <= {
            constraint["name"] for constraint in inspector.get_unique_constraints("episodes")
        }

        with engine.begin() as connection:
            media_id = connection.execute(
                text(
                    """
                    INSERT INTO media (title, alternative_titles, media_type)
                    VALUES ('Series', '[]', 'SERIES')
                    RETURNING id
                    """
                )
            ).scalar_one()
            season_id = connection.execute(
                text(
                    """
                    INSERT INTO seasons (media_id, season_number, title)
                    VALUES (:media_id, 1, 'Season 1')
                    RETURNING id
                    """
                ),
                {"media_id": media_id},
            ).scalar_one()
            connection.execute(
                text(
                    """
                    INSERT INTO episodes (season_id, episode_number, title)
                    VALUES (:season_id, 1, 'Pilot')
                    """
                ),
                {"season_id": season_id},
            )
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        downgraded = inspect(engine)
        assert not {"tags", "media_tags", "seasons", "episodes"} & set(downgraded.get_table_names())
        assert "background_url" not in {
            column["name"] for column in downgraded.get_columns("media")
        }
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
