from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "341af49d67c8"
STATISTICS_REVISION = "9d4c7a21b6e0"


def test_watch_statistics_migration_creates_and_removes_table(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"watch-statistics-{uuid4().hex}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config(project_root / "alembic.ini")
    monkeypatch.setenv("VIDEOCENTER_DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        command.upgrade(config, STATISTICS_REVISION)
        engine = create_engine(database_url)
        inspector = inspect(engine)
        assert "watch_daily_stats" in inspector.get_table_names()
        columns = {column["name"] for column in inspector.get_columns("watch_daily_stats")}
        assert {
            "stat_date",
            "media_id",
            "watched_seconds",
            "completion_count",
        } <= columns
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        assert "watch_daily_stats" not in inspect(engine).get_table_names()
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
