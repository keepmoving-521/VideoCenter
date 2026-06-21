from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "c8f42e6d1a90"
ANALYSIS_TASK_REVISION = "d91a7f2e4b63"


def test_analysis_task_migration_creates_and_removes_table(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"analysis-task-{uuid4().hex}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config(project_root / "alembic.ini")
    monkeypatch.setenv("VIDEOCENTER_DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        command.upgrade(config, ANALYSIS_TASK_REVISION)
        engine = create_engine(database_url)
        inspector = inspect(engine)
        assert "analysis_tasks" in inspector.get_table_names()
        columns = {column["name"] for column in inspector.get_columns("analysis_tasks")}
        assert {
            "resource_ids",
            "status",
            "progress",
            "processed_resources",
            "failures",
            "retry_of_task_id",
        } <= columns
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        assert "analysis_tasks" not in inspect(engine).get_table_names()
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
