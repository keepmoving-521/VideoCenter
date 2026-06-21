from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "e73b4a90c251"
COMPLETION_REVISION = "62c84ba172e1"


def test_watch_completion_migration_adds_and_removes_columns(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"watch-completion-{uuid4().hex}.db"
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
                    INSERT INTO media (id, title, media_type)
                    VALUES (1, 'Completed', 'MOVIE'), (2, 'Unfinished', 'MOVIE')
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO watch_history (
                        media_id, position_seconds, duration_seconds
                    )
                    VALUES (1, 95, 100), (2, 94, 100)
                    """
                )
            )
        engine.dispose()

        command.upgrade(config, COMPLETION_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("watch_history")}
        assert {"is_completed", "completed_at"} <= columns
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT media_id, is_completed, completed_at
                    FROM watch_history
                    ORDER BY media_id
                    """
                )
            ).all()
        assert rows[0].is_completed == 1
        assert rows[0].completed_at is not None
        assert rows[1].is_completed == 0
        assert rows[1].completed_at is None
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("watch_history")}
        assert "is_completed" not in columns
        assert "completed_at" not in columns
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
