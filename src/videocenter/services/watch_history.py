from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.models.history import WatchDailyStat, WatchHistory

COMPLETION_THRESHOLD = 0.95


def is_playback_completed(
    position_seconds: float,
    duration_seconds: float | None,
) -> bool:
    return bool(duration_seconds and position_seconds / duration_seconds >= COMPLETION_THRESHOLD)


def save_watch_history(
    db: Session,
    *,
    media_id: int,
    resource_id: int | None,
    episode_id: int | None = None,
    position_seconds: float,
    duration_seconds: float | None,
    watched_seconds_delta: float | None = None,
    track_activity: bool = False,
) -> WatchHistory:
    """Create or update the single playback history row for a media item."""
    history = db.scalar(select(WatchHistory).where(WatchHistory.media_id == media_id))
    previous_position = history.position_seconds if history is not None else 0
    was_completed = bool(history and history.is_completed)
    automatically_completed = is_playback_completed(position_seconds, duration_seconds)
    is_completed = automatically_completed or was_completed
    values = {
        "resource_id": resource_id,
        "episode_id": episode_id,
        "position_seconds": position_seconds,
        "duration_seconds": duration_seconds,
        "is_completed": is_completed,
        "completed_at": (
            history.completed_at
            if history is not None and history.completed_at is not None
            else datetime.now()
            if is_completed
            else None
        ),
    }
    if history is None:
        history = WatchHistory(media_id=media_id, **values)
        db.add(history)
    else:
        for field, value in values.items():
            setattr(history, field, value)
    if track_activity:
        inferred_seconds = max(0, position_seconds - previous_position)
        watched_seconds = (
            inferred_seconds if watched_seconds_delta is None else watched_seconds_delta
        )
        newly_completed = is_completed and not was_completed
        if watched_seconds > 0 or newly_completed:
            _record_daily_activity(
                db,
                media_id=media_id,
                watched_seconds=watched_seconds,
                completed=newly_completed,
            )
    db.commit()
    db.refresh(history)
    return history


def _record_daily_activity(
    db: Session,
    *,
    media_id: int,
    watched_seconds: float,
    completed: bool,
) -> None:
    stat_date = datetime.now().date()
    stat = db.scalar(
        select(WatchDailyStat).where(
            WatchDailyStat.stat_date == stat_date,
            WatchDailyStat.media_id == media_id,
        )
    )
    if stat is None:
        stat = WatchDailyStat(
            stat_date=stat_date,
            media_id=media_id,
            watched_seconds=watched_seconds,
            completion_count=1 if completed else 0,
        )
        db.add(stat)
        return
    stat.watched_seconds += watched_seconds
    if completed:
        stat.completion_count += 1
