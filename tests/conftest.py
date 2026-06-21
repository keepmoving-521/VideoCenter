import os
from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_PATH = PROJECT_ROOT / "data" / f"pytest-{uuid4().hex}.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"

# conftest.py is loaded before test modules. These values must be set here so
# importing videocenter.main/database can never bind to a developer database.
os.environ["VIDEOCENTER_ENVIRONMENT"] = "testing"
os.environ["VIDEOCENTER_DATABASE_URL"] = TEST_DATABASE_URL
os.environ["VIDEOCENTER_LOG_FILE_ENABLED"] = "false"
os.environ["VIDEOCENTER_DOCS_ENABLED"] = "true"

from tests.support.api import ApiAssertions  # noqa: E402
from tests.support.factories import ModelFactory  # noqa: E402
from videocenter.core.database import Base, SessionLocal, engine  # noqa: E402
from videocenter.main import app  # noqa: E402
from videocenter.models import (  # noqa: E402, F401
    DownloadTask,
    Episode,
    LocalResource,
    Media,
    Notification,
    Season,
    Tag,
    WatchHistory,
)
from videocenter.services.parse_workflow import parse_workflow_store  # noqa: E402


def assert_safe_test_database() -> None:
    if os.environ.get("VIDEOCENTER_ENVIRONMENT") != "testing":
        raise RuntimeError("Pytest database requires the testing environment")
    if not TEST_DATABASE_PATH.name.startswith("pytest-"):
        raise RuntimeError("Refusing to use a non-pytest database file")
    if TEST_DATABASE_PATH.parent != PROJECT_ROOT / "data":
        raise RuntimeError("Pytest database must be stored in the project data directory")


@pytest.fixture(scope="session", autouse=True)
def test_database() -> Generator[Path, None, None]:
    assert_safe_test_database()
    alembic_config = Config(PROJECT_ROOT / "alembic.ini")
    command.upgrade(alembic_config, "head")
    try:
        yield TEST_DATABASE_PATH
    finally:
        engine.dispose()
        TEST_DATABASE_PATH.unlink(missing_ok=True)


@pytest.fixture
def db_session(test_database: Path) -> Generator[Session, None, None]:
    del test_database
    with SessionLocal() as session:
        try:
            yield session
        finally:
            session.rollback()


@pytest.fixture
def api_client(test_database: Path) -> Generator[TestClient, None, None]:
    del test_database
    with TestClient(app) as client:
        yield client


@pytest.fixture
def api_assertions() -> ApiAssertions:
    return ApiAssertions()


@pytest.fixture
def model_factory(db_session: Session) -> ModelFactory:
    return ModelFactory(db_session)


@pytest.fixture(autouse=True)
def clean_database_between_tests(
    test_database: Path,
) -> Generator[None, None, None]:
    del test_database
    parse_workflow_store.clear()
    yield
    parse_workflow_store.clear()
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(delete(table))
