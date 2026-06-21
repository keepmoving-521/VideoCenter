from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "ec06ac928b64"
DIRECTORY_REVISION = "79c5840db912"


def test_media_directory_migration_adds_table_and_indexes(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"media-directory-{uuid4().hex}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config(project_root / "alembic.ini")

    monkeypatch.setenv("VIDEOCENTER_DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        command.upgrade(config, DIRECTORY_REVISION)
        engine = create_engine(database_url)
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("media_directories")}
        indexes = {index["name"] for index in inspector.get_indexes("media_directories")}

        assert {
            "id",
            "name",
            "path",
            "is_default",
            "is_enabled",
            "auto_scan",
            "created_at",
            "updated_at",
        } == columns
        assert {
            "ix_media_directories_is_default",
            "ix_media_directories_is_enabled",
            "ix_media_directories_name",
            "ix_media_directories_path",
        } <= indexes
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        assert "media_directories" not in inspect(engine).get_table_names()
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
