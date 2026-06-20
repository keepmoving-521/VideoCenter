from collections.abc import Iterable

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from videocenter.models.download import DownloadTask
from videocenter.models.history import WatchHistory
from videocenter.models.media import LocalResource, Media


def delete_media_records(
    db: Session,
    media_ids: Iterable[int],
) -> tuple[list[int], list[int]]:
    requested_ids = list(dict.fromkeys(media_ids))
    media_items = db.scalars(select(Media).where(Media.id.in_(requested_ids))).all()
    media_by_id = {media.id: media for media in media_items}
    deleted_ids = [media_id for media_id in requested_ids if media_id in media_by_id]
    missing_ids = [media_id for media_id in requested_ids if media_id not in media_by_id]
    if not deleted_ids:
        return deleted_ids, missing_ids

    db.execute(
        update(LocalResource).where(LocalResource.media_id.in_(deleted_ids)).values(media_id=None)
    )
    db.execute(
        update(DownloadTask).where(DownloadTask.media_id.in_(deleted_ids)).values(media_id=None)
    )
    db.execute(delete(WatchHistory).where(WatchHistory.media_id.in_(deleted_ids)))
    db.flush()

    for media_id in deleted_ids:
        db.delete(media_by_id[media_id])
    db.commit()
    return deleted_ids, missing_ids
