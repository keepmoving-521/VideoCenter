from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.core.database import get_db
from videocenter.core.exceptions import BadRequestError, ConflictError, NotFoundError
from videocenter.models.media_directory import MediaDirectory
from videocenter.schemas.media_directory import (
    MediaDirectoryCreate,
    MediaDirectoryRead,
    MediaDirectoryStorageRead,
    MediaDirectoryUpdate,
)
from videocenter.services.media_directories import (
    ensure_media_directory_unique,
    promote_default_media_directory,
    resolve_media_directory_path,
    set_default_media_directory,
)
from videocenter.services.media_storage import get_media_directory_storage

router = APIRouter()


@router.get("", response_model=list[MediaDirectoryRead])
def list_media_directories(db: Session = Depends(get_db)):
    return db.scalars(
        select(MediaDirectory).order_by(
            MediaDirectory.is_default.desc(),
            MediaDirectory.id,
        )
    ).all()


@router.get("/storage", response_model=list[MediaDirectoryStorageRead])
def list_media_directory_storage(db: Session = Depends(get_db)):
    directories = db.scalars(
        select(MediaDirectory).order_by(
            MediaDirectory.is_default.desc(),
            MediaDirectory.id,
        )
    ).all()
    return [get_media_directory_storage(db, directory) for directory in directories]


@router.get(
    "/{directory_id}/storage",
    response_model=MediaDirectoryStorageRead,
)
def get_media_directory_storage_detail(
    directory_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    directory = db.get(MediaDirectory, directory_id)
    if directory is None:
        raise NotFoundError("媒体目录不存在", code="MEDIA_DIRECTORY_NOT_FOUND")
    return get_media_directory_storage(db, directory)


@router.get("/{directory_id}", response_model=MediaDirectoryRead)
def get_media_directory(
    directory_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    directory = db.get(MediaDirectory, directory_id)
    if directory is None:
        raise NotFoundError("媒体目录不存在", code="MEDIA_DIRECTORY_NOT_FOUND")
    return directory


@router.post(
    "",
    response_model=MediaDirectoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_media_directory(
    payload: MediaDirectoryCreate,
    db: Session = Depends(get_db),
):
    try:
        normalized_path = str(resolve_media_directory_path(payload.path))
    except ValueError as exc:
        raise BadRequestError(
            str(exc),
            code="INVALID_MEDIA_DIRECTORY_PATH",
        ) from exc
    ensure_media_directory_unique(
        db,
        name=payload.name,
        path=normalized_path,
    )
    directory = MediaDirectory(
        **payload.model_dump(exclude={"path"}),
        path=normalized_path,
    )
    db.add(directory)
    db.flush()
    has_default = db.scalar(
        select(MediaDirectory.id).where(MediaDirectory.is_default.is_(True)).limit(1)
    )
    if payload.is_default or has_default is None:
        set_default_media_directory(db, directory)
    db.commit()
    db.refresh(directory)
    return directory


@router.patch("/{directory_id}", response_model=MediaDirectoryRead)
def update_media_directory(
    directory_id: Annotated[int, Path(gt=0)],
    payload: MediaDirectoryUpdate,
    db: Session = Depends(get_db),
):
    directory = db.get(MediaDirectory, directory_id)
    if directory is None:
        raise NotFoundError("媒体目录不存在", code="MEDIA_DIRECTORY_NOT_FOUND")
    values = payload.model_dump(exclude_unset=True)
    if "path" in values:
        try:
            values["path"] = str(resolve_media_directory_path(values["path"]))
        except ValueError as exc:
            raise BadRequestError(
                str(exc),
                code="INVALID_MEDIA_DIRECTORY_PATH",
            ) from exc
    name = values.get("name", directory.name)
    path = values.get("path", directory.path)
    ensure_media_directory_unique(
        db,
        name=name,
        path=path,
        exclude_id=directory.id,
    )
    if values.get("is_default") is False and directory.is_default:
        raise ConflictError(
            "默认媒体目录不能直接取消默认状态，请将其他目录设为默认",
            code="MEDIA_DIRECTORY_DEFAULT_REQUIRED",
        )
    if values.get("is_enabled") is False and directory.is_default:
        raise ConflictError(
            "默认媒体目录不能直接停用，请先将其他目录设为默认",
            code="MEDIA_DIRECTORY_DEFAULT_REQUIRED",
        )
    for field, value in values.items():
        setattr(directory, field, value)
    if values.get("is_default"):
        set_default_media_directory(db, directory)
    db.commit()
    db.refresh(directory)
    return directory


@router.delete("/{directory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_media_directory(
    directory_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
) -> None:
    directory = db.get(MediaDirectory, directory_id)
    if directory is None:
        raise NotFoundError("媒体目录不存在", code="MEDIA_DIRECTORY_NOT_FOUND")
    if directory.is_default:
        promote_default_media_directory(db, exclude_id=directory.id)
    db.delete(directory)
    db.commit()
