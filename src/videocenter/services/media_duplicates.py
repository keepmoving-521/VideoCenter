import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, selectinload

from videocenter.core.exceptions import ConflictError, NotFoundError
from videocenter.models.download import DownloadTask
from videocenter.models.history import WatchHistory
from videocenter.models.media import Episode, LocalResource, Media, Season, Tag
from videocenter.schemas.media import (
    DuplicateMediaGroup,
    DuplicateMediaItem,
    MediaDuplicatesResponse,
    MediaLibraryStats,
    MediaMergeResponse,
)

DUPLICATE_SOURCE_URL = "source_page_url"
DUPLICATE_TITLE_YEAR_TYPE = "title_year_type"


def _normalize_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _normalize_url(value: str) -> str:
    value = value.strip()
    try:
        parts = urlsplit(value)
        path = re.sub(r"/+$", "", parts.path) or "/"
        return urlunsplit(
            (
                parts.scheme.casefold(),
                parts.netloc.casefold(),
                path,
                parts.query,
                "",
            )
        )
    except ValueError:
        return value.casefold().rstrip("/")


def _duplicate_keys(media: Media) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    if media.source_page_url:
        keys.append((DUPLICATE_SOURCE_URL, _normalize_url(media.source_page_url)))
    normalized_title = _normalize_title(media.title)
    if normalized_title and media.release_year is not None:
        keys.append(
            (
                DUPLICATE_TITLE_YEAR_TYPE,
                f"{normalized_title}:{media.release_year}:{media.media_type.value}",
            )
        )
    return keys


def _duplicate_components(
    media_items: Iterable[Media],
) -> list[tuple[list[Media], list[str]]]:
    items = list(media_items)
    parent = {media.id: media.id for media in items}
    keys_by_media = {media.id: _duplicate_keys(media) for media in items}
    first_by_key: dict[tuple[str, str], int] = {}

    def find(media_id: int) -> int:
        while parent[media_id] != media_id:
            parent[media_id] = parent[parent[media_id]]
            media_id = parent[media_id]
        return media_id

    def union(first_id: int, second_id: int) -> None:
        first_root = find(first_id)
        second_root = find(second_id)
        if first_root != second_root:
            parent[second_root] = first_root

    for media in items:
        for key in keys_by_media[media.id]:
            if key in first_by_key:
                union(media.id, first_by_key[key])
            else:
                first_by_key[key] = media.id

    grouped: dict[int, list[Media]] = defaultdict(list)
    for media in items:
        grouped[find(media.id)].append(media)

    components = []
    for group in grouped.values():
        if len(group) < 2:
            continue
        reasons: set[str] = set()
        key_counts: dict[tuple[str, str], int] = defaultdict(int)
        for media in group:
            for key in keys_by_media[media.id]:
                key_counts[key] += 1
        reasons.update(key_type for (key_type, _), count in key_counts.items() if count > 1)
        components.append((sorted(group, key=lambda item: item.id), sorted(reasons)))
    return sorted(components, key=lambda component: component[0][0].id)


def detect_duplicate_media(db: Session) -> MediaDuplicatesResponse:
    media_items = db.scalars(select(Media).order_by(Media.id)).all()
    groups = [
        DuplicateMediaGroup(
            reasons=reasons,
            items=[
                DuplicateMediaItem(
                    id=media.id,
                    title=media.title,
                    media_type=media.media_type,
                    release_year=media.release_year,
                    source_site=media.source_site,
                    source_page_url=media.source_page_url,
                )
                for media in group
            ],
        )
        for group, reasons in _duplicate_components(media_items)
    ]
    return MediaDuplicatesResponse(
        group_count=len(groups),
        duplicate_media_count=sum(len(group.items) for group in groups),
        groups=groups,
    )


def _merge_string_lists(target: Media, sources: list[Media]) -> None:
    for field in (
        "alternative_titles",
        "directors",
        "actors",
        "regions",
        "languages",
        "genres",
    ):
        merged: list[str] = []
        seen: set[str] = set()
        values = [
            *getattr(target, field),
            *(item for source in sources for item in getattr(source, field)),
        ]
        for value in values:
            key = value.casefold()
            if key not in seen:
                seen.add(key)
                merged.append(value)
        setattr(target, field, merged)


def _fill_missing_metadata(target: Media, sources: list[Media]) -> None:
    for field in (
        "sort_title",
        "original_title",
        "description",
        "release_year",
        "release_date",
        "content_rating",
        "source_site",
        "source_page_url",
        "duration_minutes",
        "rating",
        "personal_rating",
        "personal_notes",
        "poster_url",
        "background_url",
    ):
        if getattr(target, field) is None:
            value = next(
                (
                    getattr(source, field)
                    for source in sources
                    if getattr(source, field) is not None
                ),
                None,
            )
            setattr(target, field, value)
    target.is_favorite = target.is_favorite or any(source.is_favorite for source in sources)
    _merge_string_lists(target, sources)


def _merge_seasons(db: Session, target: Media, sources: list[Media]) -> tuple[int, int]:
    seasons_changed = 0
    episodes_changed = 0
    target_seasons = {season.season_number: season for season in target.seasons}
    for source in sources:
        for source_season in list(source.seasons):
            target_season = target_seasons.get(source_season.season_number)
            if target_season is None:
                source_season.media = target
                target_seasons[source_season.season_number] = source_season
                seasons_changed += 1
                episodes_changed += len(source_season.episodes)
                continue

            for field in ("title", "description", "poster_url", "air_date"):
                if getattr(target_season, field) is None:
                    setattr(target_season, field, getattr(source_season, field))
            target_episodes = {
                episode.episode_number: episode for episode in target_season.episodes
            }
            for source_episode in list(source_season.episodes):
                target_episode = target_episodes.get(source_episode.episode_number)
                if target_episode is None:
                    source_episode.season = target_season
                    target_episodes[source_episode.episode_number] = source_episode
                else:
                    for field in (
                        "description",
                        "air_date",
                        "duration_minutes",
                        "thumbnail_url",
                    ):
                        if getattr(target_episode, field) is None:
                            setattr(target_episode, field, getattr(source_episode, field))
                    db.delete(source_episode)
                episodes_changed += 1
            db.flush()
            seasons_changed += 1
    return seasons_changed, episodes_changed


def _merge_watch_history(
    db: Session,
    target_media_id: int,
    source_media_ids: list[int],
) -> bool:
    histories = db.scalars(
        select(WatchHistory).where(WatchHistory.media_id.in_([target_media_id, *source_media_ids]))
    ).all()
    if not histories:
        return False
    latest = max(histories, key=lambda history: history.watched_at)
    values = {
        "resource_id": latest.resource_id,
        "position_seconds": latest.position_seconds,
        "duration_seconds": latest.duration_seconds,
        "watched_at": latest.watched_at,
    }
    db.execute(
        delete(WatchHistory).where(WatchHistory.media_id.in_([target_media_id, *source_media_ids]))
    )
    db.flush()
    db.add(WatchHistory(media_id=target_media_id, **values))
    return True


def merge_duplicate_media(
    db: Session,
    target_media_id: int,
    source_media_ids: list[int],
) -> MediaMergeResponse:
    requested_ids = [target_media_id, *source_media_ids]
    media_items = db.scalars(
        select(Media)
        .where(Media.id.in_(requested_ids))
        .options(
            selectinload(Media.tags),
            selectinload(Media.seasons).selectinload(Season.episodes),
        )
    ).all()
    media_by_id = {media.id: media for media in media_items}
    missing_ids = [media_id for media_id in requested_ids if media_id not in media_by_id]
    if missing_ids:
        raise NotFoundError(
            "待合并的影视条目不存在",
            code="MEDIA_NOT_FOUND",
            details={"missing_ids": missing_ids},
        )

    allowed_group = next(
        (
            {media.id for media in group}
            for group, _ in _duplicate_components(media_items)
            if target_media_id in {media.id for media in group}
        ),
        set(),
    )
    invalid_ids = [media_id for media_id in source_media_ids if media_id not in allowed_group]
    if invalid_ids:
        raise ConflictError(
            "只能合并检测为重复项的影视条目",
            code="MEDIA_NOT_DUPLICATE",
            details={"media_ids": invalid_ids},
        )

    target = media_by_id[target_media_id]
    sources = [media_by_id[media_id] for media_id in source_media_ids]
    _fill_missing_metadata(target, sources)

    existing_tag_ids = {tag.id for tag in target.tags}
    merged_tags = 0
    for source in sources:
        for tag in source.tags:
            if tag.id not in existing_tag_ids:
                target.tags.append(tag)
                existing_tag_ids.add(tag.id)
                merged_tags += 1

    moved_local_resources = (
        db.scalar(
            select(func.count(LocalResource.id)).where(LocalResource.media_id.in_(source_media_ids))
        )
        or 0
    )
    moved_download_tasks = (
        db.scalar(
            select(func.count(DownloadTask.id)).where(DownloadTask.media_id.in_(source_media_ids))
        )
        or 0
    )
    db.execute(
        update(LocalResource)
        .where(LocalResource.media_id.in_(source_media_ids))
        .values(media_id=target_media_id)
    )
    db.execute(
        update(DownloadTask)
        .where(DownloadTask.media_id.in_(source_media_ids))
        .values(media_id=target_media_id)
    )
    merged_watch_history = _merge_watch_history(db, target_media_id, source_media_ids)
    merged_seasons, merged_episodes = _merge_seasons(db, target, sources)
    db.flush()

    for source in sources:
        db.delete(source)
    db.commit()
    return MediaMergeResponse(
        target_media_id=target_media_id,
        merged_media_ids=source_media_ids,
        moved_local_resources=moved_local_resources,
        moved_download_tasks=moved_download_tasks,
        merged_tags=merged_tags,
        merged_seasons=merged_seasons,
        merged_episodes=merged_episodes,
        merged_watch_history=merged_watch_history,
    )


def get_media_library_stats(db: Session) -> MediaLibraryStats:
    by_type = {
        media_type.value: count
        for media_type, count in db.execute(
            select(Media.media_type, func.count(Media.id)).group_by(Media.media_type)
        )
    }
    by_status = {
        media_status.value: count
        for media_status, count in db.execute(
            select(Media.status, func.count(Media.id)).group_by(Media.status)
        )
    }
    return MediaLibraryStats(
        total_media=db.scalar(select(func.count(Media.id))) or 0,
        favorite_media=(
            db.scalar(select(func.count(Media.id)).where(Media.is_favorite.is_(True))) or 0
        ),
        media_with_local_resources=(
            db.scalar(
                select(func.count(func.distinct(LocalResource.media_id))).where(
                    LocalResource.media_id.is_not(None)
                )
            )
            or 0
        ),
        total_local_resources=db.scalar(select(func.count(LocalResource.id))) or 0,
        total_download_tasks=db.scalar(select(func.count(DownloadTask.id))) or 0,
        total_tags=db.scalar(select(func.count(Tag.id))) or 0,
        total_seasons=db.scalar(select(func.count(Season.id))) or 0,
        total_episodes=db.scalar(select(func.count(Episode.id))) or 0,
        by_type=by_type,
        by_status=by_status,
    )
