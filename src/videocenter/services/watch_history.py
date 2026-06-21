from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.models.history import WatchHistory

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
    position_seconds: float,
    duration_seconds: float | None,
) -> WatchHistory:
    """Create or update the single playback history row for a media item."""
    history = db.scalar(select(WatchHistory).where(WatchHistory.media_id == media_id))
    automatically_completed = is_playback_completed(position_seconds, duration_seconds)
    is_completed = automatically_completed or bool(history and history.is_completed)
    values = {
        "resource_id": resource_id,
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
    db.commit()
    db.refresh(history)
    return history
