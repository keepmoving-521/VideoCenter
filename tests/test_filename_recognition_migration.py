from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "f809bb912daf"
FILENAME_REVISION = "c35a942f71de"
EXPECTED_COLUMNS = {
    "detected_media_type",
    "parsed_title",
    "parsed_release_year",
    "parsed_season_number",
    "parsed_episode_number",
}


def test_filename_recognition_migration_adds_and_removes_fields(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"filename-recognition-{uuid4().hex}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config(project_root / "alembic.ini")

    monkeypatch.setenv("VIDEOCENTER_DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        command.upgrade(config, FILENAME_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("local_resources")}
        assert EXPECTED_COLUMNS <= columns
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        columns = {column["name"] for column in inspect(engine).get_columns("local_resources")}
        assert EXPECTED_COLUMNS.isdisjoint(columns)
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
