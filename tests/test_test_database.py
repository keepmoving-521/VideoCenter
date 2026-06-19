from pathlib import Path

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from videocenter.core.config import AppEnvironment, get_settings
from videocenter.core.database import engine
from videocenter.models.media import Media

EXPECTED_TABLES = {
    "alembic_version",
    "download_tasks",
    "episodes",
    "local_resources",
    "media",
    "media_tags",
    "seasons",
    "tags",
    "watch_history",
}


def test_pytest_uses_dedicated_database(test_database: Path):
    settings = get_settings()

    assert settings.environment == AppEnvironment.TESTING
    assert Path(engine.url.database).resolve() == test_database.resolve()
    assert test_database.name.startswith("pytest-")
    assert test_database.name != "videocenter.db"


def test_test_database_is_created_by_alembic():
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES


def test_db_session_fixture_uses_test_database(db_session: Session):
    db_session.add(Media(title="Test-only movie"))
    db_session.commit()

    title = db_session.scalar(select(Media.title))
    assert title == "Test-only movie"
