from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from videocenter.core.database import get_db
from videocenter.core.exceptions import BadRequestError, ConflictError, NotFoundError
from videocenter.models.media import (
    Episode,
    Media,
    MediaType,
    Season,
    Tag,
    media_tags,
)
from videocenter.schemas.catalog import (
    EpisodeCreate,
    EpisodeDetailRead,
    EpisodeRead,
    EpisodeUpdate,
    MediaHierarchyRead,
    MediaTagsUpdate,
    SeasonCreate,
    SeasonRead,
    SeasonUpdate,
    SeasonWithEpisodesRead,
    TagCreate,
    TagDetailRead,
    TagRead,
    TagUpdate,
)

router = APIRouter()


def get_media_or_404(db: Session, media_id: int) -> Media:
    media = db.get(Media, media_id)
    if media is None:
        raise NotFoundError("影视条目不存在", code="MEDIA_NOT_FOUND")
    return media


def get_season_or_404(db: Session, season_id: int) -> Season:
    season = db.get(Season, season_id)
    if season is None:
        raise NotFoundError("电视剧季不存在", code="SEASON_NOT_FOUND")
    return season


def get_episode_or_404(db: Session, episode_id: int) -> Episode:
    episode = db.get(Episode, episode_id)
    if episode is None:
        raise NotFoundError("电视剧分集不存在", code="EPISODE_NOT_FOUND")
    return episode


def load_season_with_episodes(db: Session, season_id: int) -> Season:
    season = db.scalar(
        select(Season).options(selectinload(Season.episodes)).where(Season.id == season_id)
    )
    if season is None:
        raise NotFoundError("电视剧季不存在", code="SEASON_NOT_FOUND")
    return season


def commit_or_conflict(db: Session, *, code: str, message: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(message, code=code) from exc


@router.get("/tags", response_model=list[TagRead], tags=["影视标签"])
def list_tags(db: Session = Depends(get_db)):
    return db.scalars(select(Tag).order_by(Tag.name)).all()


@router.post(
    "/tags",
    response_model=TagRead,
    status_code=status.HTTP_201_CREATED,
    tags=["影视标签"],
)
def create_tag(payload: TagCreate, db: Session = Depends(get_db)):
    tag = Tag(name=payload.name, normalized_name=payload.name.casefold())
    db.add(tag)
    commit_or_conflict(
        db,
        code="TAG_ALREADY_EXISTS",
        message="同名标签已存在",
    )
    db.refresh(tag)
    return tag


@router.get(
    "/tags/{tag_id}",
    response_model=TagDetailRead,
    tags=["影视标签"],
)
def get_tag(
    tag_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise NotFoundError("影视标签不存在", code="TAG_NOT_FOUND")
    media_count = db.scalar(
        select(func.count()).select_from(media_tags).where(media_tags.c.tag_id == tag_id)
    )
    return TagDetailRead(
        id=tag.id,
        name=tag.name,
        created_at=tag.created_at,
        media_count=media_count or 0,
    )


@router.patch(
    "/tags/{tag_id}",
    response_model=TagRead,
    tags=["影视标签"],
)
def update_tag(
    tag_id: Annotated[int, Path(gt=0)],
    payload: TagUpdate,
    db: Session = Depends(get_db),
):
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise NotFoundError("影视标签不存在", code="TAG_NOT_FOUND")
    tag.name = payload.name
    tag.normalized_name = payload.name.casefold()
    commit_or_conflict(
        db,
        code="TAG_ALREADY_EXISTS",
        message="同名标签已存在",
    )
    db.refresh(tag)
    return tag


@router.delete(
    "/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["影视标签"],
)
def delete_tag(
    tag_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
) -> None:
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise NotFoundError("影视标签不存在", code="TAG_NOT_FOUND")
    db.delete(tag)
    db.commit()


@router.put(
    "/media/{media_id}/tags",
    response_model=list[TagRead],
    tags=["影视标签"],
)
def replace_media_tags(
    media_id: Annotated[int, Path(gt=0)],
    payload: MediaTagsUpdate,
    db: Session = Depends(get_db),
):
    media = get_media_or_404(db, media_id)
    tags = (
        db.scalars(select(Tag).where(Tag.id.in_(payload.tag_ids))).all() if payload.tag_ids else []
    )
    if len(tags) != len(payload.tag_ids):
        raise NotFoundError("一个或多个影视标签不存在", code="TAG_NOT_FOUND")
    tags_by_id = {tag.id: tag for tag in tags}
    media.tags = [tags_by_id[tag_id] for tag_id in payload.tag_ids]
    db.commit()
    return media.tags


@router.post(
    "/media/{media_id}/tags/{tag_id}",
    response_model=list[TagRead],
    tags=["影视标签"],
)
def add_media_tag(
    media_id: Annotated[int, Path(gt=0)],
    tag_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    media = get_media_or_404(db, media_id)
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise NotFoundError("影视标签不存在", code="TAG_NOT_FOUND")
    if tag not in media.tags:
        media.tags.append(tag)
        db.commit()
    return sorted(media.tags, key=lambda item: item.name)


@router.delete(
    "/media/{media_id}/tags/{tag_id}",
    response_model=list[TagRead],
    tags=["影视标签"],
)
def remove_media_tag(
    media_id: Annotated[int, Path(gt=0)],
    tag_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    media = get_media_or_404(db, media_id)
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise NotFoundError("影视标签不存在", code="TAG_NOT_FOUND")
    if tag in media.tags:
        media.tags.remove(tag)
        db.commit()
    return sorted(media.tags, key=lambda item: item.name)


@router.get(
    "/media/{media_id}/hierarchy",
    response_model=MediaHierarchyRead,
    tags=["影视目录"],
)
def get_media_hierarchy(
    media_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    media = db.scalar(
        select(Media)
        .options(selectinload(Media.seasons).selectinload(Season.episodes))
        .where(Media.id == media_id)
    )
    if media is None:
        raise NotFoundError("影视条目不存在", code="MEDIA_NOT_FOUND")
    return MediaHierarchyRead(
        media_id=media.id,
        title=media.title,
        seasons=media.seasons,
    )


@router.get(
    "/media/{media_id}/seasons",
    response_model=list[SeasonRead],
    tags=["电视剧季"],
)
def list_seasons(
    media_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    get_media_or_404(db, media_id)
    return db.scalars(
        select(Season).where(Season.media_id == media_id).order_by(Season.season_number)
    ).all()


@router.post(
    "/media/{media_id}/seasons",
    response_model=SeasonRead,
    status_code=status.HTTP_201_CREATED,
    tags=["电视剧季"],
)
def create_season(
    media_id: Annotated[int, Path(gt=0)],
    payload: SeasonCreate,
    db: Session = Depends(get_db),
):
    media = get_media_or_404(db, media_id)
    if media.media_type != MediaType.SERIES:
        raise BadRequestError(
            "只有电视剧类型的影视条目可以创建季",
            code="SEASON_REQUIRES_SERIES",
        )
    season = Season(media_id=media_id, **payload.to_model_values())
    db.add(season)
    commit_or_conflict(
        db,
        code="SEASON_NUMBER_CONFLICT",
        message="该影视条目下已存在相同季号",
    )
    db.refresh(season)
    return season


@router.patch(
    "/seasons/{season_id}",
    response_model=SeasonRead,
    tags=["电视剧季"],
)
def update_season(
    season_id: Annotated[int, Path(gt=0)],
    payload: SeasonUpdate,
    db: Session = Depends(get_db),
):
    season = get_season_or_404(db, season_id)
    for field, value in payload.to_model_values().items():
        setattr(season, field, value)
    commit_or_conflict(
        db,
        code="SEASON_NUMBER_CONFLICT",
        message="该影视条目下已存在相同季号",
    )
    db.refresh(season)
    return season


@router.get(
    "/seasons/{season_id}",
    response_model=SeasonWithEpisodesRead,
    tags=["电视剧季"],
)
def get_season(
    season_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    return load_season_with_episodes(db, season_id)


@router.delete(
    "/seasons/{season_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["电视剧季"],
)
def delete_season(
    season_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
) -> None:
    season = get_season_or_404(db, season_id)
    db.delete(season)
    db.commit()


@router.get(
    "/seasons/{season_id}/episodes",
    response_model=list[EpisodeRead],
    tags=["电视剧分集"],
)
def list_episodes(
    season_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    get_season_or_404(db, season_id)
    return db.scalars(
        select(Episode).where(Episode.season_id == season_id).order_by(Episode.episode_number)
    ).all()


@router.post(
    "/seasons/{season_id}/episodes",
    response_model=EpisodeRead,
    status_code=status.HTTP_201_CREATED,
    tags=["电视剧分集"],
)
def create_episode(
    season_id: Annotated[int, Path(gt=0)],
    payload: EpisodeCreate,
    db: Session = Depends(get_db),
):
    get_season_or_404(db, season_id)
    episode = Episode(season_id=season_id, **payload.to_model_values())
    db.add(episode)
    commit_or_conflict(
        db,
        code="EPISODE_NUMBER_CONFLICT",
        message="该季下已存在相同集号",
    )
    db.refresh(episode)
    return episode


@router.patch(
    "/episodes/{episode_id}",
    response_model=EpisodeRead,
    tags=["电视剧分集"],
)
def update_episode(
    episode_id: Annotated[int, Path(gt=0)],
    payload: EpisodeUpdate,
    db: Session = Depends(get_db),
):
    episode = get_episode_or_404(db, episode_id)
    for field, value in payload.to_model_values().items():
        setattr(episode, field, value)
    commit_or_conflict(
        db,
        code="EPISODE_NUMBER_CONFLICT",
        message="该季下已存在相同集号",
    )
    db.refresh(episode)
    return episode


@router.get(
    "/episodes/{episode_id}",
    response_model=EpisodeDetailRead,
    tags=["电视剧分集"],
)
def get_episode(
    episode_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    episode = db.scalar(
        select(Episode).options(selectinload(Episode.season)).where(Episode.id == episode_id)
    )
    if episode is None:
        raise NotFoundError("电视剧分集不存在", code="EPISODE_NOT_FOUND")
    return EpisodeDetailRead.model_validate(
        {
            **EpisodeRead.model_validate(episode).model_dump(),
            "media_id": episode.season.media_id,
            "season_number": episode.season.season_number,
        }
    )


@router.delete(
    "/episodes/{episode_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["电视剧分集"],
)
def delete_episode(
    episode_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
) -> None:
    episode = get_episode_or_404(db, episode_id)
    db.delete(episode)
    db.commit()
