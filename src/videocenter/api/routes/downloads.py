from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.core.database import get_db
from videocenter.core.exceptions import BadRequestError, NotFoundError
from videocenter.models.download import DownloadTask
from videocenter.models.media import Media
from videocenter.schemas.download import DownloadCreate, DownloadRead
from videocenter.services.downloads import cancel_download, safe_target_name, start_download

router = APIRouter()


@router.get("", response_model=list[DownloadRead])
def list_downloads(db: Session = Depends(get_db)):
    return db.scalars(select(DownloadTask).order_by(DownloadTask.id.desc())).all()


@router.post("", response_model=DownloadRead, status_code=status.HTTP_202_ACCEPTED)
def create_download(payload: DownloadCreate, db: Session = Depends(get_db)):
    if payload.media_id is not None and not db.get(Media, payload.media_id):
        raise NotFoundError("影视条目不存在", code="MEDIA_NOT_FOUND")
    try:
        target_name = safe_target_name(payload.target_name)
    except ValueError as exc:
        raise BadRequestError(str(exc), code="INVALID_TARGET_NAME") from exc
    task = DownloadTask(
        media_id=payload.media_id,
        source_url=str(payload.source_url),
        target_name=target_name,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    start_download(task.id)
    return task


@router.get("/{task_id}", response_model=DownloadRead)
def get_download(task_id: int, db: Session = Depends(get_db)):
    task = db.get(DownloadTask, task_id)
    if not task:
        raise NotFoundError("下载任务不存在", code="DOWNLOAD_TASK_NOT_FOUND")
    return task


@router.post("/{task_id}/cancel", response_model=DownloadRead)
def cancel(task_id: int, db: Session = Depends(get_db)):
    task = db.get(DownloadTask, task_id)
    if not task:
        raise NotFoundError("下载任务不存在", code="DOWNLOAD_TASK_NOT_FOUND")
    return cancel_download(db, task)
