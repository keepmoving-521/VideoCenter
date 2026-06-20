from abc import ABC, abstractmethod
from datetime import date
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def validate_http_url(value: str, *, field_label: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"{field_label}必须是有效的 HTTP 或 HTTPS 地址")
    return value


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def normalize_text_items(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        if not item:
            continue
        key = item.casefold()
        if key not in seen:
            seen.add(key)
            normalized.append(item)
    return tuple(normalized)


class ParserDataModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class ParsedMediaType(StrEnum):
    MOVIE = "movie"
    SERIES = "series"
    DOCUMENTARY = "documentary"
    ANIMATION = "animation"
    VARIETY_SHOW = "variety_show"
    SHORT_FILM = "short_film"
    OTHER = "other"


class ParsedResourceType(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"
    SUBTITLE = "subtitle"
    OTHER = "other"


class ParseRequest(ParserDataModel):
    source_url: str
    preferred_language: str | None = Field(default=None, max_length=50)

    def __init__(self, source_url: str, **data: Any) -> None:
        super().__init__(source_url=source_url, **data)

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        return validate_http_url(value, field_label="资源页面地址")


class ParsedDownload(ParserDataModel):
    source_url: str
    target_name: str | None = Field(default=None, min_length=1, max_length=512)
    quality: str | None = Field(default=None, min_length=1, max_length=100)
    mime_type: str | None = Field(default=None, min_length=1, max_length=128)
    resource_type: ParsedResourceType = ParsedResourceType.VIDEO
    language: str | None = Field(default=None, min_length=1, max_length=50)
    file_size: int | None = Field(default=None, gt=0)
    headers: dict[str, str] = Field(default_factory=dict)

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        return validate_http_url(value, field_label="下载地址")


class ParsedEpisode(ParserDataModel):
    episode_number: int = Field(gt=0, le=100_000)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)
    air_date: date | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=100_000)
    thumbnail_url: str | None = None
    downloads: tuple[ParsedDownload, ...] = ()

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @field_validator("thumbnail_url")
    @classmethod
    def validate_thumbnail_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_http_url(value, field_label="分集缩略图地址")


class ParsedSeason(ParserDataModel):
    season_number: int = Field(ge=0, le=10_000)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)
    poster_url: str | None = None
    air_date: date | None = None
    episodes: tuple[ParsedEpisode, ...] = ()

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @field_validator("poster_url")
    @classmethod
    def validate_poster_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_http_url(value, field_label="季海报地址")

    @model_validator(mode="after")
    def validate_unique_episode_numbers(self) -> "ParsedSeason":
        numbers = [episode.episode_number for episode in self.episodes]
        if len(numbers) != len(set(numbers)):
            raise ValueError("同一季的分集编号不能重复")
        return self


class ParseResult(ParserDataModel):
    title: str = Field(min_length=1, max_length=255)
    source_site: str = Field(min_length=1, max_length=100)
    source_page_url: str
    original_title: str | None = Field(default=None, min_length=1, max_length=255)
    alternative_titles: tuple[str, ...] = ()
    media_type: ParsedMediaType = ParsedMediaType.MOVIE
    description: str | None = Field(default=None, max_length=10_000)
    release_date: date | None = None
    content_rating: str | None = Field(default=None, min_length=1, max_length=32)
    directors: tuple[str, ...] = ()
    actors: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    genres: tuple[str, ...] = ()
    duration_minutes: int | None = Field(default=None, gt=0, le=100_000)
    rating: float | None = Field(default=None, ge=0, le=10)
    poster_url: str | None = None
    background_url: str | None = None
    tags: tuple[str, ...] = ()
    downloads: tuple[ParsedDownload, ...] = ()
    seasons: tuple[ParsedSeason, ...] = ()
    extra: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_page_url")
    @classmethod
    def validate_source_page_url(cls, value: str) -> str:
        return validate_http_url(value, field_label="来源页面地址")

    @field_validator("poster_url", "background_url")
    @classmethod
    def validate_artwork_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_http_url(value, field_label="图片地址")

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @field_validator(
        "alternative_titles",
        "directors",
        "actors",
        "regions",
        "languages",
        "genres",
        "tags",
    )
    @classmethod
    def normalize_text_lists(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return normalize_text_items(value)

    @model_validator(mode="after")
    def validate_hierarchy(self) -> "ParseResult":
        season_numbers = [season.season_number for season in self.seasons]
        if len(season_numbers) != len(set(season_numbers)):
            raise ValueError("同一影片的季编号不能重复")
        if self.seasons and self.media_type != ParsedMediaType.SERIES:
            raise ValueError("只有电视剧类型的解析结果可以包含季")
        return self

    def to_media_values(self) -> dict[str, Any]:
        """Return fields that can be passed to the Media model."""
        excluded = {"downloads", "seasons", "tags", "extra"}
        return self.model_dump(mode="json", exclude=excluded)


class ResourceParser(ABC):
    """Contract implemented by resource-page parsers."""

    name: str
    priority: int = 0

    @abstractmethod
    def supports(self, request: ParseRequest) -> bool:
        """Return whether this parser can handle the resource page."""

    @abstractmethod
    async def parse(self, request: ParseRequest) -> ParseResult:
        """Parse one resource page into the standard VideoCenter result."""
