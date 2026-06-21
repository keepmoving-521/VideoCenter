from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "e8c1d24ab639"
CAPACITY_REVISION = "f20a6b183e74"


def test_media_directory_capacity_migration_adds_defaults(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"capacity-warning-{uuid4().hex}.db"
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
                    INSERT INTO media_directories (name, path)
                    VALUES ('Existing', 'C:/media')
                    """
                )
            )
        engine.dispose()

        command.upgrade(config, CAPACITY_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("media_directories")}
        constraints = {
            constraint["name"]
            for constraint in inspect(engine).get_check_constraints("media_directories")
        }
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT capacity_warning_enabled,
                           capacity_warning_threshold_percent
                    FROM media_directories
                    """
                )
            ).one()
        assert {
            "capacity_warning_enabled",
            "capacity_warning_threshold_percent",
        } <= columns
        assert row.capacity_warning_enabled == 1
        assert row.capacity_warning_threshold_percent == 90
        assert "ck_media_directory_capacity_warning_threshold" in constraints
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("media_directories")}
        assert "capacity_warning_enabled" not in columns
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
