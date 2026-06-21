from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "e191f7270b02"
AVAILABILITY_REVISION = "f809bb912daf"


def test_resource_availability_migration_adds_fields_and_defaults(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"resource-availability-{uuid4().hex}.db"
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
                    INSERT INTO local_resources (
                        file_path,
                        file_name,
                        file_size,
                        mime_type
                    )
                    VALUES (
                        'C:/media/movie.mp4',
                        'movie.mp4',
                        100,
                        'video/mp4'
                    )
                    """
                )
            )
        engine.dispose()

        command.upgrade(config, AVAILABILITY_REVISION)
        engine = create_engine(database_url)
        inspector = inspect(engine)
        resource_columns = {column["name"] for column in inspector.get_columns("local_resources")}
        scan_columns = {column["name"] for column in inspector.get_columns("scan_tasks")}
        indexes = {index["name"] for index in inspector.get_indexes("local_resources")}
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT is_available, missing_at FROM local_resources")
            ).one()

        assert {"is_available", "missing_at"} <= resource_columns
        assert {"missing_files", "restored_files"} <= scan_columns
        assert "ix_local_resources_is_available" in indexes
        assert row.is_available == 1
        assert row.missing_at is None
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("local_resources")}
        assert "is_available" not in columns
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
