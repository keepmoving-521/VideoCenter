from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "df3d06a94df5"
NOTIFICATION_REVISION = "ec06ac928b64"


def test_download_notification_migration_adds_table_and_indexes(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"download-notification-{uuid4().hex}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config(project_root / "alembic.ini")

    monkeypatch.setenv("VIDEOCENTER_DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        command.upgrade(config, NOTIFICATION_REVISION)
        engine = create_engine(database_url)
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("notifications")}
        indexes = {index["name"] for index in inspector.get_indexes("notifications")}
        unique_constraints = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("notifications")
        }

        assert {
            "id",
            "notification_type",
            "download_task_id",
            "media_id",
            "title",
            "message",
            "read_at",
            "created_at",
        } == columns
        assert {
            "ix_notifications_created_at",
            "ix_notifications_download_task_id",
            "ix_notifications_media_id",
            "ix_notifications_notification_type",
            "ix_notifications_read_at",
        } <= indexes
        assert ("download_task_id",) in unique_constraints
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        assert "notifications" not in inspect(engine).get_table_names()
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
