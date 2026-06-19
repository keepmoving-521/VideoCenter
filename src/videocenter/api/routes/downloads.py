from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.core.database import get_db
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
        raise HTTPException(status_code=404, detail="影视条目不存在")
    try:
        target_name = safe_target_name(payload.target_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
        raise HTTPException(status_code=404, detail="下载任务不存在")
    return task


@router.post("/{task_id}/cancel", response_model=DownloadRead)
def cancel(task_id: int, db: Session = Depends(get_db)):
    task = db.get(DownloadTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="下载任务不存在")
    return cancel_download(db, task)
