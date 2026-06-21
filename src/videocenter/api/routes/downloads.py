from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.core.database import get_db
from videocenter.core.exceptions import BadRequestError, ConflictError, NotFoundError
from videocenter.models.download import DownloadStatus, DownloadTask
from videocenter.models.media import Media
from videocenter.schemas.download import DownloadCreate, DownloadRead
from videocenter.services.downloads import (
    cancel_download,
    generate_target_name,
    normalized_download_source,
    pause_download,
    resolve_download_directory,
    resume_download,
    retry_download,
    safe_target_name,
    select_download_provider,
    start_download,
    update_media_download_status,
)

router = APIRouter()


@router.get("", response_model=list[DownloadRead])
def list_downloads(db: Session = Depends(get_db)):
    return db.scalars(select(DownloadTask).order_by(DownloadTask.id.desc())).all()


@router.post("", response_model=DownloadRead, status_code=status.HTTP_202_ACCEPTED)
def create_download(payload: DownloadCreate, db: Session = Depends(get_db)):
    media = db.get(Media, payload.media_id) if payload.media_id is not None else None
    if payload.media_id is not None and media is None:
        raise NotFoundError("影视条目不存在", code="MEDIA_NOT_FOUND")
    source_url = normalized_download_source(str(payload.source_url))
    downloader_name = select_download_provider(source_url, payload.downloader.value)
    duplicate = db.scalar(
        select(DownloadTask)
        .where(
            DownloadTask.source_url == source_url,
            DownloadTask.status != DownloadStatus.CANCELLED,
        )
        .order_by(DownloadTask.id.desc())
    )
    if duplicate is not None:
        raise ConflictError(
            "该资源已经存在下载任务",
            code="DOWNLOAD_ALREADY_EXISTS",
            details={
                "task_id": duplicate.id,
                "status": duplicate.status.value,
            },
        )
    try:
        _, target_directory = resolve_download_directory(payload.target_directory)
    except ValueError as exc:
        raise BadRequestError(
            str(exc),
            code="INVALID_TARGET_DIRECTORY",
        ) from exc
    try:
        target_name = (
            safe_target_name(payload.target_name)
            if payload.target_name is not None
            else generate_target_name(
                source_url,
                media_title=media.title if media is not None else None,
            )
        )
    except ValueError as exc:
        raise BadRequestError(str(exc), code="INVALID_TARGET_NAME") from exc
    task = DownloadTask(
        media_id=payload.media_id,
        source_url=source_url,
        target_name=target_name,
        target_directory=target_directory,
        downloader_name=downloader_name,
        expected_sha256=payload.expected_sha256,
        priority=payload.priority,
    )
    db.add(task)
    db.flush()
    update_media_download_status(db, task.media_id)
    db.commit()
    db.refresh(task)
    start_download(task.id, priority=task.priority)
    return task


@router.get("/{task_id}", response_model=DownloadRead)
def get_download(
    task_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    task = db.get(DownloadTask, task_id)
    if not task:
        raise NotFoundError("下载任务不存在", code="DOWNLOAD_TASK_NOT_FOUND")
    return task


@router.post("/{task_id}/cancel", response_model=DownloadRead)
def cancel(
    task_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    task = db.get(DownloadTask, task_id)
    if not task:
        raise NotFoundError("下载任务不存在", code="DOWNLOAD_TASK_NOT_FOUND")
    return cancel_download(db, task)


@router.post("/{task_id}/pause", response_model=DownloadRead)
def pause(
    task_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    task = db.get(DownloadTask, task_id)
    if not task:
        raise NotFoundError("下载任务不存在", code="DOWNLOAD_TASK_NOT_FOUND")
    return pause_download(db, task)


@router.post("/{task_id}/resume", response_model=DownloadRead)
def resume(
    task_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    task = db.get(DownloadTask, task_id)
    if not task:
        raise NotFoundError("下载任务不存在", code="DOWNLOAD_TASK_NOT_FOUND")
    return resume_download(db, task)


@router.post("/{task_id}/retry", response_model=DownloadRead)
def retry(
    task_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    task = db.get(DownloadTask, task_id)
    if not task:
        raise NotFoundError("下载任务不存在", code="DOWNLOAD_TASK_NOT_FOUND")
    return retry_download(db, task)
