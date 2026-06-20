from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class ParseRequest:
    source_url: str
    preferred_language: str | None = None

    def __post_init__(self) -> None:
        parsed = urlparse(self.source_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("资源页面地址必须是有效的 HTTP 或 HTTPS 地址")


@dataclass(frozen=True, slots=True)
class ParsedDownload:
    source_url: str
    target_name: str | None = None
    quality: str | None = None
    mime_type: str | None = None


@dataclass(frozen=True, slots=True)
class ParsedEpisode:
    episode_number: int
    title: str
    description: str | None = None
    air_date: str | None = None
    duration_minutes: int | None = None
    thumbnail_url: str | None = None
    downloads: tuple[ParsedDownload, ...] = ()


@dataclass(frozen=True, slots=True)
class ParsedSeason:
    season_number: int
    title: str | None = None
    description: str | None = None
    poster_url: str | None = None
    air_date: str | None = None
    episodes: tuple[ParsedEpisode, ...] = ()


@dataclass(frozen=True, slots=True)
class ParseResult:
    title: str
    source_site: str
    source_page_url: str
    original_title: str | None = None
    alternative_titles: tuple[str, ...] = ()
    media_type: str = "movie"
    description: str | None = None
    release_date: str | None = None
    content_rating: str | None = None
    directors: tuple[str, ...] = ()
    actors: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    genres: tuple[str, ...] = ()
    duration_minutes: int | None = None
    rating: float | None = None
    poster_url: str | None = None
    background_url: str | None = None
    tags: tuple[str, ...] = ()
    downloads: tuple[ParsedDownload, ...] = ()
    seasons: tuple[ParsedSeason, ...] = ()
    extra: dict[str, Any] = field(default_factory=dict)


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
