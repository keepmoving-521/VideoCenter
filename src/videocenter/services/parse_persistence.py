from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.core.exceptions import ConflictError
from videocenter.models.media import Episode, Media, MediaType, Season, Tag
from videocenter.services.parsers import ParsedResourceType, ParseResult


def save_parse_result(
    db: Session,
    result: ParseResult,
) -> tuple[Media, dict[str, int]]:
    existing_id = db.scalar(select(Media.id).where(Media.source_page_url == result.source_page_url))
    if existing_id is not None:
        raise ConflictError(
            "该来源页面已保存到影视库",
            code="PARSED_MEDIA_ALREADY_EXISTS",
            details={"media_id": existing_id},
        )

    media = Media(
        title=result.title,
        original_title=result.original_title,
        alternative_titles=list(result.alternative_titles),
        media_type=MediaType(result.media_type.value),
        description=result.description,
        release_year=result.release_year,
        release_date=result.release_date,
        content_rating=result.content_rating,
        source_site=result.source_site,
        source_page_url=result.source_page_url,
        directors=list(result.directors),
        actors=list(result.actors),
        regions=list(result.regions),
        languages=list(result.languages),
        genres=list(result.genres),
        duration_minutes=result.duration_minutes,
        rating=result.rating,
        poster_url=result.poster_url,
        background_url=result.background_url,
    )
    db.add(media)
    db.flush()

    tags_created = 0
    for tag_name in result.tags:
        normalized_name = tag_name.casefold()
        tag = db.scalar(select(Tag).where(Tag.normalized_name == normalized_name))
        if tag is None:
            tag = Tag(name=tag_name, normalized_name=normalized_name)
            db.add(tag)
            tags_created += 1
        media.tags.append(tag)

    episodes_created = 0
    for parsed_season in result.seasons:
        season = Season(
            media_id=media.id,
            season_number=parsed_season.season_number,
            title=parsed_season.title,
            description=parsed_season.description,
            poster_url=parsed_season.poster_url,
            air_date=parsed_season.air_date,
        )
        db.add(season)
        db.flush()
        for parsed_episode in parsed_season.episodes:
            db.add(
                Episode(
                    season_id=season.id,
                    episode_number=parsed_episode.episode_number,
                    title=parsed_episode.title,
                    description=parsed_episode.description,
                    air_date=parsed_episode.air_date,
                    duration_minutes=parsed_episode.duration_minutes,
                    thumbnail_url=parsed_episode.thumbnail_url,
                )
            )
            episodes_created += 1

    all_downloads = list(result.downloads)
    for parsed_season in result.seasons:
        for parsed_episode in parsed_season.episodes:
            all_downloads.extend(parsed_episode.downloads)

    stats = {
        "tags_created": tags_created,
        "seasons_created": len(result.seasons),
        "episodes_created": episodes_created,
        "downloads_detected": sum(
            item.resource_type == ParsedResourceType.VIDEO for item in all_downloads
        ),
        "subtitles_detected": sum(
            item.resource_type == ParsedResourceType.SUBTITLE for item in all_downloads
        ),
    }
    db.commit()
    db.refresh(media)
    return media, stats


def suggested_download_name(source_url: str, fallback: str) -> str:
    name = PurePosixPath(source_url.split("?", 1)[0]).name
    return name or fallback
