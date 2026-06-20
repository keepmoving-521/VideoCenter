from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from videocenter.core.config import get_settings

PREVIOUS_REVISION = "b81d5ca75147"
PAUSE_REVISION = "cf6e704f63c2"


def test_paused_download_status_supports_upgrade_and_downgrade(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    database_path = project_root / "data" / f"download-pause-{uuid4().hex}.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config(project_root / "alembic.ini")

    monkeypatch.setenv("VIDEOCENTER_DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        command.upgrade(config, PAUSE_REVISION)
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
                        'PAUSED',
                        25,
                        250
                    )
                    """
                )
            )
        engine.dispose()

        command.downgrade(config, PREVIOUS_REVISION)
        engine = create_engine(database_url)
        with engine.connect() as connection:
            status = connection.execute(text("SELECT status FROM download_tasks")).scalar_one()
        assert status == "WAITING"
        engine.dispose()
    finally:
        get_settings.cache_clear()
        database_path.unlink(missing_ok=True)
