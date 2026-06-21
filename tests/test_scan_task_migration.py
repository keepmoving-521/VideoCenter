from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "79c5840db912"
SCAN_REVISION = "e191f7270b02"


def test_scan_task_migration_adds_table_and_resource_timestamp(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"scan-task-{uuid4().hex}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config(project_root / "alembic.ini")

    monkeypatch.setenv("VIDEOCENTER_DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        command.upgrade(config, SCAN_REVISION)
        engine = create_engine(database_url)
        inspector = inspect(engine)
        scan_columns = {column["name"] for column in inspector.get_columns("scan_tasks")}
        resource_columns = {column["name"] for column in inspector.get_columns("local_resources")}
        assert {
            "id",
            "path",
            "media_id",
            "incremental",
            "status",
            "progress",
            "total_files",
            "processed_files",
            "discovered_files",
            "added_files",
            "updated_files",
            "skipped_files",
            "error_message",
            "created_at",
            "started_at",
            "completed_at",
        } == scan_columns
        assert "modified_at_ns" in resource_columns
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        inspector = inspect(engine)
        assert "scan_tasks" not in inspector.get_table_names()
        assert "modified_at_ns" not in {
            column["name"] for column in inspector.get_columns("local_resources")
        }
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
