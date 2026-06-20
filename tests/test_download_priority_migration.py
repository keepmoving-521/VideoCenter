from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "cf6e704f63c2"
PRIORITY_REVISION = "ce532e7c91a4"


def test_download_priority_migration_adds_default_and_constraint(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"download-priority-{uuid4().hex}.db"
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
                    INSERT INTO download_tasks (
                        source_url,
                        target_name,
                        status,
                        progress,
                        downloaded_bytes
                    )
                    VALUES (
                        'https://example.com/video.mp4',
                        'video.mp4',
                        'WAITING',
                        0,
                        0
                    )
                    """
                )
            )
        engine.dispose()

        command.upgrade(config, PRIORITY_REVISION)
        engine = create_engine(database_url)
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("download_tasks")}
        indexes = {index["name"] for index in inspector.get_indexes("download_tasks")}
        checks = {
            constraint["name"] for constraint in inspector.get_check_constraints("download_tasks")
        }
        with engine.connect() as connection:
            priority = connection.execute(text("SELECT priority FROM download_tasks")).scalar_one()

        assert "priority" in columns
        assert "ix_download_tasks_priority" in indexes
        assert "ck_download_priority_range" in checks
        assert priority == 0
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("download_tasks")}
        assert "priority" not in columns
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
