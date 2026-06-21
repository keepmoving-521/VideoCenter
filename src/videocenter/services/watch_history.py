from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.models.history import WatchHistory


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
    values = {
        "resource_id": resource_id,
        "position_seconds": position_seconds,
        "duration_seconds": duration_seconds,
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
