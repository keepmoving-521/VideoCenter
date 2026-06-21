import mimetypes
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from videocenter.core.config import get_settings
from videocenter.core.exceptions import ConflictError, NotFoundError
from videocenter.models.history import WatchHistory
from videocenter.models.media import LocalResource
from videocenter.services.downloads import update_media_download_status
from videocenter.services.local_library import VIDEO_EXTENSIONS
from videocenter.services.video_filename import parse_video_filename

TRASH_DIRECTORY_NAME = ".videocenter-trash"


def rename_local_resource(
    db: Session,
    *,
    resource_id: int,
    new_file_name: str,
) -> LocalResource:
    resource = _get_resource(db, resource_id)
    source = _validated_resource_path(resource)
    if not source.is_file():
        raise ConflictError("本地文件不存在，无法重命名", code="LOCAL_FILE_MISSING")

    normalized_name = _validate_file_name(new_file_name)
    target = (source.parent / normalized_name).resolve()
    _ensure_in_media_root(target)
    if target == source:
        return resource
    if target.exists():
        raise ConflictError("目标文件名已存在", code="LOCAL_FILE_NAME_CONFLICT")

    source.rename(target)
    try:
        stat = target.stat()
        parsed = parse_video_filename(target.name)
        resource.file_path = str(target)
        resource.file_name = target.name
        resource.file_size = stat.st_size
        resource.modified_at_ns = stat.st_mtime_ns
        resource.mime_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        resource.detected_media_type = parsed.media_type.value
        resource.parsed_title = parsed.title
        resource.parsed_release_year = parsed.release_year
        resource.parsed_season_number = parsed.season_number
        resource.parsed_episode_number = parsed.episode_number
        db.commit()
    except Exception:
        db.rollback()
        target.rename(source)
        raise
    db.refresh(resource)
    return resource


def safely_delete_local_resource(db: Session, *, resource_id: int) -> LocalResource:
    resource = _get_resource(db, resource_id)
    source = _validated_resource_path(resource)
    if not source.is_file():
        raise ConflictError("本地文件不存在，无法安全删除", code="LOCAL_FILE_MISSING")

    trash_directory = (
        get_settings().media_root / TRASH_DIRECTORY_NAME / datetime.now(UTC).strftime("%Y%m%d")
    )
    trash_directory.mkdir(parents=True, exist_ok=True)
    target = trash_directory / f"{uuid4().hex}-{source.name}"
    source.rename(target)
    media_id = resource.media_id
    try:
        resource.is_available = False
        resource.missing_at = datetime.now()
        db.flush()
        update_media_download_status(db, media_id)
        db.commit()
    except Exception:
        db.rollback()
        source.parent.mkdir(parents=True, exist_ok=True)
        target.rename(source)
        raise
    db.refresh(resource)
    return resource


def cleanup_invalid_local_resources(db: Session) -> list[int]:
    resources = db.scalars(
        select(LocalResource)
        .where(LocalResource.is_available.is_(False))
        .order_by(LocalResource.id)
    ).all()
    invalid = [resource for resource in resources if not Path(resource.file_path).exists()]
    if not invalid:
        return []

    resource_ids = [resource.id for resource in invalid]
    affected_media_ids = {
        resource.media_id for resource in invalid if resource.media_id is not None
    }
    db.execute(
        update(WatchHistory)
        .where(WatchHistory.resource_id.in_(resource_ids))
        .values(resource_id=None)
    )
    for resource in invalid:
        db.delete(resource)
    db.flush()
    for media_id in affected_media_ids:
        update_media_download_status(db, media_id)
    db.commit()
    return resource_ids


def _get_resource(db: Session, resource_id: int) -> LocalResource:
    resource = db.get(LocalResource, resource_id)
    if resource is None:
        raise NotFoundError("本地资源不存在", code="LOCAL_RESOURCE_NOT_FOUND")
    return resource


def _validated_resource_path(resource: LocalResource) -> Path:
    path = Path(resource.file_path).resolve()
    _ensure_in_media_root(path)
    if TRASH_DIRECTORY_NAME in path.parts:
        raise ConflictError("不能操作回收站中的文件", code="LOCAL_FILE_IN_TRASH")
    return path


def _ensure_in_media_root(path: Path) -> None:
    if not path.is_relative_to(get_settings().media_root):
        raise ConflictError("只能操作媒体根目录内的文件", code="UNSAFE_LOCAL_FILE_PATH")


def _validate_file_name(value: str) -> str:
    name = value.strip()
    if (
        not name
        or Path(name).name != name
        or "/" in name
        or "\\" in name
        or os.path.altsep is not None
        and os.path.altsep in name
    ):
        raise ConflictError("文件名不能包含目录路径", code="INVALID_LOCAL_FILE_NAME")
    if Path(name).suffix.casefold() not in VIDEO_EXTENSIONS:
        raise ConflictError("文件扩展名不是支持的视频格式", code="INVALID_VIDEO_EXTENSION")
    return name
