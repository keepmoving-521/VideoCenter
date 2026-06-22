from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "4b6d19ea83f2"
TASK_LOG_REVISION = "a8c31f72d590"


def test_background_task_log_migration_creates_and_removes_table(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"background-task-log-{uuid4().hex}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config(project_root / "alembic.ini")
    monkeypatch.setenv("VIDEOCENTER_DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        command.upgrade(config, TASK_LOG_REVISION)
        engine = create_engine(database_url)
        inspector = inspect(engine)
        assert "background_task_logs" in inspector.get_table_names()
        columns = {column["name"] for column in inspector.get_columns("background_task_logs")}
        assert {
            "task_id",
            "event",
            "message",
            "status",
            "progress",
            "details",
            "created_at",
        } <= columns
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        assert "background_task_logs" not in inspect(engine).get_table_names()
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
