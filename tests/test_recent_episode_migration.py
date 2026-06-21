from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "62c84ba172e1"
RECENT_EPISODE_REVISION = "341af49d67c8"


def test_recent_episode_migration_adds_and_removes_episode_reference(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"recent-episode-{uuid4().hex}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config(project_root / "alembic.ini")
    monkeypatch.setenv("VIDEOCENTER_DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        command.upgrade(config, RECENT_EPISODE_REVISION)
        engine = create_engine(database_url)
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("watch_history")}
        assert "episode_id" in columns
        foreign_keys = inspector.get_foreign_keys("watch_history")
        assert any(
            foreign_key["referred_table"] == "episodes"
            and foreign_key["constrained_columns"] == ["episode_id"]
            for foreign_key in foreign_keys
        )
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("watch_history")}
        assert "episode_id" not in columns
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
