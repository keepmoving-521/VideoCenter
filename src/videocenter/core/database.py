from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from videocenter.core.config import get_settings

settings = get_settings()


def prepare_database_directory(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return
    database_path = Path(database_url.removeprefix("sqlite:///"))
    database_path.parent.mkdir(parents=True, exist_ok=True)


def create_database_engine(database_url: str, *, echo: bool = False):
    prepare_database_directory(database_url)
    return create_engine(
        database_url,
        echo=echo,
        connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
    )


def create_session_factory(database_engine):
    return sessionmaker(
        bind=database_engine,
        autoflush=False,
        expire_on_commit=False,
    )


engine = create_database_engine(settings.database_url, echo=settings.database_echo)
SessionLocal = create_session_factory(engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
