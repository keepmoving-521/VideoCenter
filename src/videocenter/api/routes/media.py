from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session, selectinload

from videocenter.core.database import get_db
from videocenter.core.exceptions import NotFoundError
from videocenter.models.media import Media, MediaStatus, MediaType, Season
from videocenter.schemas.media import (
    MediaCreate,
    MediaDetailRead,
    MediaPage,
    MediaRead,
    MediaSortField,
    MediaUpdate,
    SortOrder,
)

router = APIRouter()


@router.get("", response_model=MediaPage)
def list_media(
    query: Annotated[
        str | None,
        Query(min_length=1, max_length=100, pattern=r".*\S.*"),
    ] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    is_favorite: bool | None = Query(default=None),
    media_type: MediaType | None = Query(default=None),
    release_year: int | None = Query(default=None, ge=1888, le=2100),
    media_status: MediaStatus | None = Query(default=None, alias="status"),
    source_site: Annotated[
        str | None,
        Query(min_length=1, max_length=100, pattern=r".*\S.*"),
    ] = None,
    sort_by: MediaSortField = Query(default=MediaSortField.CREATED_AT),
    sort_order: SortOrder = Query(default=SortOrder.DESC),
    db: Session = Depends(get_db),
):
    filters = []
    if query:
        escaped_query = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        title_pattern = f"%{escaped_query}%"
        filters.append(
            or_(
                Media.title.ilike(title_pattern, escape="\\"),
                Media.sort_title.ilike(title_pattern, escape="\\"),
                Media.original_title.ilike(title_pattern, escape="\\"),
                cast(Media.alternative_titles, String).ilike(
                    title_pattern,
                    escape="\\",
                ),
            )
        )
    if is_favorite is not None:
        filters.append(Media.is_favorite == is_favorite)
    if media_type is not None:
        filters.append(Media.media_type == media_type)
    if release_year is not None:
        filters.append(Media.release_year == release_year)
    if media_status is not None:
        filters.append(Media.status == media_status)
    if source_site is not None:
        filters.append(Media.source_site.ilike(source_site.strip()))

    sort_columns = {
        MediaSortField.CREATED_AT: Media.created_at,
        MediaSortField.UPDATED_AT: Media.updated_at,
        MediaSortField.TITLE: Media.title,
        MediaSortField.RELEASE_YEAR: Media.release_year,
        MediaSortField.RATING: Media.rating,
        MediaSortField.PERSONAL_RATING: Media.personal_rating,
    }
    sort_column = sort_columns[sort_by]
    order_expression = (
        sort_column.asc().nulls_last()
        if sort_order == SortOrder.ASC
        else sort_column.desc().nulls_last()
    )

    total = db.scalar(select(func.count(Media.id)).where(*filters)) or 0
    total_pages = (total + page_size - 1) // page_size
    statement = (
        select(Media)
        .where(*filters)
        .options(
            selectinload(Media.resources),
            selectinload(Media.tags),
        )
        .order_by(order_expression, Media.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = db.scalars(statement).all()
    return MediaPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1 and total_pages > 0,
    )


@router.post("", response_model=MediaRead, status_code=status.HTTP_201_CREATED)
def create_media(payload: MediaCreate, db: Session = Depends(get_db)):
    media = Media(**payload.to_model_values())
    db.add(media)
    db.commit()
    return get_media(media.id, db)


@router.get("/{media_id}", response_model=MediaDetailRead)
def get_media(
    media_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    media = db.scalar(
        select(Media)
        .options(
            selectinload(Media.resources),
            selectinload(Media.tags),
            selectinload(Media.seasons).selectinload(Season.episodes),
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
