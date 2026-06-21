from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from videocenter.core.config import get_settings

EXPECTED_TABLES = {
    "alembic_version",
    "analysis_tasks",
    "download_tasks",
    "episodes",
    "local_resources",
    "media",
    "media_directories",
    "media_tags",
    "notifications",
    "scan_tasks",
    "seasons",
    "tags",
    "watch_history",
}


def test_initial_migration_upgrade_downgrade_and_reupgrade(
    monkeypatch,
):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"migration_test_{uuid4().hex}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config(project_root / "alembic.ini")

    monkeypatch.setenv("VIDEOCENTER_DATABASE_URL", database_url)
    get_settings.cache_clear()
    engine = None

    try:
        command.upgrade(config, "head")
        engine = create_engine(database_url)
        assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES
        engine.dispose()
        engine = None

        command.downgrade(config, "base")
        engine = create_engine(database_url)
        assert set(inspect(engine).get_table_names()) == {"alembic_version"}
        engine.dispose()
        engine = None

        command.upgrade(config, "head")
        engine = create_engine(database_url)
        assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES
        engine.dispose()
        engine = None
    finally:
        if engine is not None:
            engine.dispose()
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
