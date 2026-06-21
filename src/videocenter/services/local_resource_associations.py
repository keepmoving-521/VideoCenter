from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.core.exceptions import NotFoundError
from videocenter.models.media import LocalResource, Media
from videocenter.services.downloads import update_media_download_status


def associate_local_resources(
    db: Session,
    *,
    resource_ids: list[int],
    media_id: int | None,
) -> tuple[list[LocalResource], list[int]]:
    if media_id is not None and db.get(Media, media_id) is None:
        raise NotFoundError("影视条目不存在", code="MEDIA_NOT_FOUND")

    resources_by_id = {
        resource.id: resource
        for resource in db.scalars(
            select(LocalResource).where(LocalResource.id.in_(resource_ids))
        ).all()
    }
    resources = [
        resources_by_id[resource_id]
        for resource_id in resource_ids
        if resource_id in resources_by_id
    ]
    missing_ids = [
        resource_id for resource_id in resource_ids if resource_id not in resources_by_id
    ]
    affected_media_ids = {
        resource.media_id for resource in resources if resource.media_id is not None
    }
    if media_id is not None:
        affected_media_ids.add(media_id)

    for resource in resources:
        resource.media_id = media_id

    db.flush()
    for affected_media_id in affected_media_ids:
        update_media_download_status(db, affected_media_id)
    db.commit()
    for resource in resources:
        db.refresh(resource)
    return resources, missing_ids
