from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from videocenter.core.database import get_db
from videocenter.core.exceptions import BadRequestError, NotFoundError
from videocenter.models.history import WatchHistory
from videocenter.models.media import Episode, LocalResource, Media, Season
from videocenter.schemas.history import (
    HistoryBatchDeleteRequest,
    HistoryBatchDeleteResponse,
    HistoryClearResponse,
    HistoryListItem,
    HistoryMediaSummary,
    HistoryPage,
    HistoryRead,
    HistoryUpsert,
    NextEpisodeRead,
    WatchedEpisodeRead,
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
    if payload.episode_id is not None:
        episode = db.scalar(
            select(Episode)
            .join(Season, Season.id == Episode.season_id)
            .where(
                Episode.id == payload.episode_id,
                Season.media_id == payload.media_id,
            )
        )
        if episode is None:
            raise BadRequestError(
                "分集不存在或不属于指定影视条目",
                code="EPISODE_MEDIA_MISMATCH",
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


@router.post("/batch-delete", response_model=HistoryBatchDeleteResponse)
def batch_delete_history(
    payload: HistoryBatchDeleteRequest,
    db: Session = Depends(get_db),
):
    existing_media_ids = list(
        db.scalars(
            select(WatchHistory.media_id).where(WatchHistory.media_id.in_(payload.media_ids))
        ).all()
    )
    existing_set = set(existing_media_ids)
    deleted_media_ids = [media_id for media_id in payload.media_ids if media_id in existing_set]
    missing_media_ids = [media_id for media_id in payload.media_ids if media_id not in existing_set]
    if deleted_media_ids:
        db.execute(delete(WatchHistory).where(WatchHistory.media_id.in_(deleted_media_ids)))
        db.commit()
    return HistoryBatchDeleteResponse(
        deleted_count=len(deleted_media_ids),
        deleted_media_ids=deleted_media_ids,
        missing_media_ids=missing_media_ids,
    )


@router.delete("/clear", response_model=HistoryClearResponse)
def clear_history(db: Session = Depends(get_db)):
    deleted_count = db.scalar(select(func.count(WatchHistory.id))) or 0
    if deleted_count:
        db.execute(delete(WatchHistory))
        db.commit()
    return HistoryClearResponse(deleted_count=deleted_count)


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
        episode_id=history.episode_id if history is not None else None,
        position_seconds=position_seconds,
        duration_seconds=duration_seconds,
    )
    if not saved.is_completed:
        saved.is_completed = True
        saved.completed_at = datetime.now()
        db.commit()
        db.refresh(saved)
    return saved


@router.get("/{media_id}/recent-episode", response_model=WatchedEpisodeRead)
def get_recent_watched_episode(
    media_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    if db.get(Media, media_id) is None:
        raise NotFoundError("影视条目不存在", code="MEDIA_NOT_FOUND")
    row = db.execute(
        select(WatchHistory, Episode, Season)
        .join(Episode, Episode.id == WatchHistory.episode_id)
        .join(Season, Season.id == Episode.season_id)
        .where(WatchHistory.media_id == media_id)
    ).one_or_none()
    if row is None:
        raise NotFoundError("尚未记录最近观看分集", code="RECENT_EPISODE_NOT_FOUND")
    history, episode, season = row
    return WatchedEpisodeRead(
        id=episode.id,
        media_id=media_id,
        season_id=season.id,
        season_number=season.season_number,
        episode_number=episode.episode_number,
        title=episode.title,
        thumbnail_url=episode.thumbnail_url,
        resource_id=history.resource_id,
        stream_url=(
            f"/api/v1/stream/{history.resource_id}" if history.resource_id is not None else None
        ),
        position_seconds=history.position_seconds,
        duration_seconds=history.duration_seconds,
        is_completed=history.is_completed,
        watched_at=history.watched_at,
    )


@router.get("/{media_id}/next-episode", response_model=NextEpisodeRead)
def recommend_next_episode(
    media_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    if db.get(Media, media_id) is None:
        raise NotFoundError("影视条目不存在", code="MEDIA_NOT_FOUND")
    current = db.execute(
        select(Episode, Season)
        .join(Season, Season.id == Episode.season_id)
        .join(WatchHistory, WatchHistory.episode_id == Episode.id)
        .where(WatchHistory.media_id == media_id)
    ).one_or_none()
    if current is None:
        raise NotFoundError("尚未记录最近观看分集", code="RECENT_EPISODE_NOT_FOUND")
    current_episode, current_season = current
    next_row = db.execute(
        select(Episode, Season)
        .join(Season, Season.id == Episode.season_id)
        .where(
            Season.media_id == media_id,
            (
                (Season.season_number > current_season.season_number)
                | (
                    (Season.season_number == current_season.season_number)
                    & (Episode.episode_number > current_episode.episode_number)
                )
            ),
        )
        .order_by(Season.season_number, Episode.episode_number)
        .limit(1)
    ).one_or_none()
    if next_row is None:
        raise NotFoundError("没有可推荐的下一集", code="NEXT_EPISODE_NOT_FOUND")
    episode, season = next_row
    resource = db.scalar(
        select(LocalResource)
        .where(
            LocalResource.media_id == media_id,
            LocalResource.parsed_season_number == season.season_number,
            LocalResource.parsed_episode_number == episode.episode_number,
            LocalResource.is_available.is_(True),
        )
        .order_by(LocalResource.id)
    )
    return NextEpisodeRead(
        media_id=media_id,
        current_episode_id=current_episode.id,
        id=episode.id,
        season_id=season.id,
        season_number=season.season_number,
        episode_number=episode.episode_number,
        title=episode.title,
        description=episode.description,
        duration_minutes=episode.duration_minutes,
        thumbnail_url=episode.thumbnail_url,
        resource_id=resource.id if resource is not None else None,
        playable=resource is not None,
        stream_url=f"/api/v1/stream/{resource.id}" if resource is not None else None,
    )


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
