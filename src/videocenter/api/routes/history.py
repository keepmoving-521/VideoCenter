from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.core.database import get_db
from videocenter.core.exceptions import NotFoundError
from videocenter.models.history import WatchHistory
from videocenter.models.media import LocalResource, Media
from videocenter.schemas.history import HistoryRead, HistoryUpsert

router = APIRouter()


@router.get("", response_model=list[HistoryRead])
def list_history(db: Session = Depends(get_db)):
    return db.scalars(
        select(WatchHistory).order_by(WatchHistory.watched_at.desc())
    ).all()


@router.put("", response_model=HistoryRead)
def save_history(payload: HistoryUpsert, db: Session = Depends(get_db)):
    if not db.get(Media, payload.media_id):
        raise NotFoundError("影视条目不存在", code="MEDIA_NOT_FOUND")
    if payload.resource_id is not None and not db.get(LocalResource, payload.resource_id):
        raise NotFoundError("本地资源不存在", code="LOCAL_RESOURCE_NOT_FOUND")
    history = db.scalar(
        select(WatchHistory).where(WatchHistory.media_id == payload.media_id)
    )
    if history is None:
        history = WatchHistory(**payload.model_dump())
        db.add(history)
    else:
        for field, value in payload.model_dump().items():
            setattr(history, field, value)
    db.commit()
    db.refresh(history)
    return history


@router.delete("/{media_id}", status_code=204)
def delete_history(media_id: int, db: Session = Depends(get_db)) -> None:
    history = db.scalar(
        select(WatchHistory).where(WatchHistory.media_id == media_id)
    )
    if not history:
        raise NotFoundError("观看记录不存在", code="WATCH_HISTORY_NOT_FOUND")
    db.delete(history)
    db.commit()
