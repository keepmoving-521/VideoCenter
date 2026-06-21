from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from videocenter.core.config import get_settings
from videocenter.core.exceptions import ConflictError
from videocenter.models.media_directory import MediaDirectory


def resolve_media_directory_path(value: str) -> Path:
    root = get_settings().media_root.resolve()
    requested = Path(value)
    candidate = (
        requested.expanduser().resolve()
        if requested.is_absolute()
        else (root / requested).resolve()
    )
    if not candidate.is_relative_to(root):
        raise ValueError("媒体目录必须位于媒体根目录内")
    if not candidate.is_dir():
        raise ValueError("媒体目录不存在")
    return candidate


def ensure_media_directory_unique(
    db: Session,
    *,
    name: str,
    path: str,
    exclude_id: int | None = None,
) -> None:
    statement = select(MediaDirectory).where(
        (MediaDirectory.name == name) | (MediaDirectory.path == path)
    )
    if exclude_id is not None:
        statement = statement.where(MediaDirectory.id != exclude_id)
    existing = db.scalar(statement)
    if existing is None:
        return
    code = "MEDIA_DIRECTORY_NAME_EXISTS" if existing.name == name else "MEDIA_DIRECTORY_PATH_EXISTS"
    raise ConflictError("媒体目录名称或路径已存在", code=code)


def set_default_media_directory(db: Session, directory: MediaDirectory) -> None:
    db.execute(
        update(MediaDirectory).where(MediaDirectory.id != directory.id).values(is_default=False)
    )
    directory.is_default = True
