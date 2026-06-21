from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "c35a942f71de"
HASH_REVISION = "e8c1d24ab639"


def test_local_resource_hash_migration_adds_field_and_index(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"resource-hash-{uuid4().hex}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config(project_root / "alembic.ini")
    monkeypatch.setenv("VIDEOCENTER_DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        command.upgrade(config, HASH_REVISION)
        engine = create_engine(database_url)
        inspector = inspect(engine)
        columns = {column["name"] for column in inspector.get_columns("local_resources")}
        indexes = {index["name"] for index in inspector.get_indexes("local_resources")}
        assert "checksum_sha256" in columns
        assert "ix_local_resources_checksum_sha256" in indexes
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("local_resources")}
        assert "checksum_sha256" not in columns
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
