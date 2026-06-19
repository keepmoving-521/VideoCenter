from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from videocenter.core.database import get_db
from videocenter.core.exceptions import NotFoundError
from videocenter.models.media import Media
from videocenter.schemas.media import MediaCreate, MediaRead, MediaUpdate

router = APIRouter()


@router.get("", response_model=list[MediaRead])
def list_media(
    query: Annotated[
        str | None,
        Query(min_length=1, max_length=100, pattern=r".*\S.*"),
    ] = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    statement = select(Media).options(
        selectinload(Media.resources),
        selectinload(Media.tags),
    )
    if query:
        statement = statement.where(
            or_(Media.title.contains(query), Media.original_title.contains(query))
        )
    return db.scalars(statement.offset(offset).limit(limit).order_by(Media.id.desc())).all()


@router.post("", response_model=MediaRead, status_code=status.HTTP_201_CREATED)
def create_media(payload: MediaCreate, db: Session = Depends(get_db)):
    media = Media(**payload.to_model_values())
    db.add(media)
    db.commit()
    return get_media(media.id, db)


@router.get("/{media_id}", response_model=MediaRead)
def get_media(
    media_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    media = db.scalar(
        select(Media)
        .options(
            selectinload(Media.resources),
            selectinload(Media.tags),
        )
        .where(Media.id == media_id)
    )
    if not media:
        raise NotFoundError("影视条目不存在", code="MEDIA_NOT_FOUND")
    return media


@router.patch("/{media_id}", response_model=MediaRead)
def update_media(
    media_id: Annotated[int, Path(gt=0)],
    payload: MediaUpdate,
    db: Session = Depends(get_db),
):
    media = db.get(Media, media_id)
    if not media:
        raise NotFoundError("影视条目不存在", code="MEDIA_NOT_FOUND")
    for field, value in payload.to_model_values().items():
        setattr(media, field, value)
    db.commit()
    return get_media(media_id, db)


@router.delete("/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_media(
    media_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
) -> None:
    media = db.get(Media, media_id)
    if not media:
        raise NotFoundError("影视条目不存在", code="MEDIA_NOT_FOUND")
    db.delete(media)
    db.commit()
