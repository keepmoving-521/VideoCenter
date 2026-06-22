from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from videocenter.core.config import get_settings
from videocenter.models.background_task import BackgroundTask, BackgroundTaskType

PREVIOUS_REVISION = "73e2b8f940a1"
RESOURCE_PARSE_REVISION = "4b6d19ea83f2"


def test_resource_parse_task_type_migration_accepts_new_type(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"resource-parse-type-{uuid4().hex}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config(project_root / "alembic.ini")
    monkeypatch.setenv("VIDEOCENTER_DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        command.upgrade(config, RESOURCE_PARSE_REVISION)
        engine = create_engine(database_url)
        with Session(engine) as session:
            session.add(
                BackgroundTask(
                    task_type=BackgroundTaskType.RESOURCE_PARSE,
                    title="Parse resource",
                )
            )
            session.commit()
            assert session.query(BackgroundTask).one().task_type == (
                BackgroundTaskType.RESOURCE_PARSE
            )
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
