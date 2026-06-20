from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "2e9d613cec84"
STATUS_REVISION = "6f17a72c8e41"


def test_download_status_migration_converts_existing_tasks(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"download-status-{uuid4().hex}.db"
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
                        progress
                    )
                    VALUES
                        ('https://example.com/waiting.mp4', 'waiting.mp4', 'PENDING', 0),
                        ('https://example.com/running.mp4', 'running.mp4', 'RUNNING', 50)
                    """
                )
            )
        engine.dispose()

        command.upgrade(config, STATUS_REVISION)
        engine = create_engine(database_url)
        with engine.connect() as connection:
            statuses = (
                connection.execute(text("SELECT status FROM download_tasks ORDER BY id"))
                .scalars()
                .all()
            )
        assert statuses == ["WAITING", "DOWNLOADING"]
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        with engine.connect() as connection:
            statuses = (
                connection.execute(text("SELECT status FROM download_tasks ORDER BY id"))
                .scalars()
                .all()
            )
        assert statuses == ["PENDING", "RUNNING"]
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
