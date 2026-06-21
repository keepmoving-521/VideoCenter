from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from videocenter.core.database import get_db
from videocenter.core.exceptions import BadRequestError, NotFoundError
from videocenter.models.history import WatchHistory
from videocenter.models.media import LocalResource, Media
from videocenter.schemas.history import (
    HistoryListItem,
    HistoryMediaSummary,
    HistoryPage,
    HistoryRead,
    HistoryUpsert,
)
from videocenter.services.watch_history import save_watch_history

router = APIRouter()


def _history_page(
    db: Session,
    *,
    page: int,
    page_size: int,
    continue_watching_only: bool,
) -> HistoryPage:
    filters = []
    if continue_watching_only:
        filters.extend(
            [
                WatchHistory.position_seconds > 0,
                WatchHistory.is_completed.is_(False),
            ]
        )
    total = (
        db.scalar(
            select(func.count(WatchHistory.id))
            .join(Media, Media.id == WatchHistory.media_id)
            .where(*filters)
        )
        or 0
    )
    total_pages = (total + page_size - 1) // page_size
    rows = db.execute(
        select(WatchHistory, Media)
        .join(Media, Media.id == WatchHistory.media_id)
        .where(*filters)
        .order_by(WatchHistory.watched_at.desc(), WatchHistory.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        HistoryListItem(
            **HistoryRead.model_validate(history).model_dump(),
            media=HistoryMediaSummary(
                id=media.id,
                title=media.title,
                media_type=media.media_type,
                release_year=media.release_year,
                poster_url=media.poster_url,
            ),
        )
        for history, media in rows
    ]
    return HistoryPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1 and total_pages > 0,
    )


@router.get("", response_model=list[HistoryRead])
def list_history(db: Session = Depends(get_db)):
    return db.scalars(select(WatchHistory).order_by(WatchHistory.watched_at.desc())).all()


@router.put("", response_model=HistoryRead)
def save_history(payload: HistoryUpsert, db: Session = Depends(get_db)):
    if not db.get(Media, payload.media_id):
        raise NotFoundError("影视条目不存在", code="MEDIA_NOT_FOUND")
    if payload.resource_id is not None:
        resource = db.get(LocalResource, payload.resource_id)
        if resource is None:
            raise NotFoundError("本地资源不存在", code="LOCAL_RESOURCE_NOT_FOUND")
        if resource.media_id not in {None, payload.media_id}:
            raise BadRequestError(
                "本地资源不属于指定影视条目",
                code="RESOURCE_MEDIA_MISMATCH",
            )
    return save_watch_history(db, **payload.model_dump())


@router.get("/continue-watching", response_model=HistoryPage)
def list_continue_watching(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return _history_page(
        db,
        page=page,
        page_size=page_size,
        continue_watching_only=True,
    )


@router.get("/recent", response_model=HistoryPage)
def list_recently_watched(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return _history_page(
        db,
        page=page,
        page_size=page_size,
        continue_watching_only=False,
    )


@router.put("/{media_id}/completed", response_model=HistoryRead)
def mark_media_completed(
    media_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    media = db.get(Media, media_id)
    if media is None:
        raise NotFoundError("影视条目不存在", code="MEDIA_NOT_FOUND")
    history = db.scalar(select(WatchHistory).where(WatchHistory.media_id == media_id))
    resource = (
        db.get(LocalResource, history.resource_id)
        if history is not None and history.resource_id is not None
        else db.scalar(
            select(LocalResource)
            .where(LocalResource.media_id == media_id)
            .order_by(LocalResource.id)
        )
    )
    duration_seconds = (history.duration_seconds if history is not None else None) or (
        resource.duration_seconds if resource is not None else None
    )
    if duration_seconds is None and media.duration_minutes is not None:
        duration_seconds = media.duration_minutes * 60
    position_seconds = (
        duration_seconds
        if duration_seconds is not None
        else history.position_seconds
        if history is not None
        else 0
    )
    saved = save_watch_history(
        db,
        media_id=media_id,
        resource_id=resource.id if resource is not None else None,
        position_seconds=position_seconds,
        duration_seconds=duration_seconds,
    )
    if not saved.is_completed:
        saved.is_completed = True
        saved.completed_at = datetime.now()
        db.commit()
        db.refresh(saved)
    return saved


@router.put("/{media_id}/unwatched", status_code=204)
def mark_media_unwatched(
    media_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
) -> None:
    if db.get(Media, media_id) is None:
        raise NotFoundError("影视条目不存在", code="MEDIA_NOT_FOUND")
    history = db.scalar(select(WatchHistory).where(WatchHistory.media_id == media_id))
    if history is not None:
        db.delete(history)
        db.commit()


@router.get("/{media_id}", response_model=HistoryRead)
def get_history(
    media_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    if db.get(Media, media_id) is None:
        raise NotFoundError("影视条目不存在", code="MEDIA_NOT_FOUND")
    history = db.scalar(select(WatchHistory).where(WatchHistory.media_id == media_id))
    if history is None:
        raise NotFoundError("观看记录不存在", code="WATCH_HISTORY_NOT_FOUND")
    return history


@router.delete("/{media_id}", status_code=204)
def delete_history(
    media_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
) -> None:
    history = db.scalar(select(WatchHistory).where(WatchHistory.media_id == media_id))
    if not history:
        raise NotFoundError("观看记录不存在", code="WATCH_HISTORY_NOT_FOUND")
    db.delete(history)
    db.commit()
