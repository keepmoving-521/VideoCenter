import asyncio
import json
import re
import urllib.request
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

from videocenter.services.parsers.base import (
    ParsedDownload,
    ParsedEpisode,
    ParsedMediaType,
    ParsedResourceType,
    ParsedSeason,
    ParseRequest,
    ParseResult,
    ResourceParser,
)

MAX_PAGE_BYTES = 2 * 1024 * 1024
USER_AGENT = "VideoCenter/0.1 (+resource-parser)"
ISO_DURATION_PATTERN = re.compile(
    r"^PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$",
    re.IGNORECASE,
)
NAME_SEPARATOR_PATTERN = re.compile(r"[,;|，；、]+")
YEAR_PATTERN = re.compile(r"(?<!\d)(18(?:8[8-9]|9\d)|19\d{2}|20\d{2}|2100)(?!\d)")


@dataclass(frozen=True, slots=True)
class WebPageResponse:
    url: str
    content_type: str
    text: str


WebPageFetcher = Callable[[str], Awaitable[WebPageResponse]]


def _fetch_web_page_sync(url: str) -> WebPageResponse:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml"}:
            raise ValueError("资源地址返回的不是 HTML 网页")
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_PAGE_BYTES:
            raise ValueError("网页内容超过允许的大小")
        body = response.read(MAX_PAGE_BYTES + 1)
        if len(body) > MAX_PAGE_BYTES:
            raise ValueError("网页内容超过允许的大小")
        charset = response.headers.get_content_charset() or "utf-8"
        return WebPageResponse(
            url=response.geturl(),
            content_type=content_type,
            text=body.decode(charset, errors="replace"),
        )


async def fetch_web_page(url: str) -> WebPageResponse:
    return await asyncio.to_thread(_fetch_web_page_sync, url)


class WebPageMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self.meta_values: dict[str, list[str]] = {}
        self.canonical_url: str | None = None
        self.json_ld_blocks: list[str] = []
        self.media_elements: list[dict[str, str]] = []
        self._in_title = False
        self._in_json_ld = False
        self._script_parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attributes = {
            key.casefold(): value.strip()
            for key, value in attrs
            if value is not None and value.strip()
        }
        tag = tag.casefold()
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = attributes.get("property") or attributes.get("name") or attributes.get("itemprop")
            content = attributes.get("content")
            if key and content:
                normalized_key = key.casefold()
                self.meta.setdefault(normalized_key, content)
                self.meta_values.setdefault(normalized_key, []).append(content)
        elif tag == "link" and "canonical" in attributes.get("rel", "").casefold().split():
            self.canonical_url = attributes.get("href")
        elif tag in {"video", "source"} and attributes.get("src"):
            self.media_elements.append(
                {
                    "resource_type": "video",
                    **attributes,
                }
            )
        elif (
            tag == "track"
            and attributes.get("src")
            and attributes.get("kind", "subtitles").casefold() in {"subtitles", "captions"}
        ):
            self.media_elements.append(
                {
                    "resource_type": "subtitle",
                    **attributes,
                }
            )
        elif tag == "script" and attributes.get("type", "").casefold() == "application/ld+json":
            self._in_json_ld = True
            self._script_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag == "title":
            self._in_title = False
        elif tag == "script" and self._in_json_ld:
            self._in_json_ld = False
            block = "".join(self._script_parts).strip()
            if block:
                self.json_ld_blocks.append(block)
            self._script_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._in_json_ld:
            self._script_parts.append(data)

    @property
    def title(self) -> str | None:
        title = " ".join("".join(self.title_parts).split())
        return title or None


def iter_json_ld_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, list):
        for item in value:
            yield from iter_json_ld_objects(item)
    elif isinstance(value, dict):
        yield value
        graph = value.get("@graph")
        if graph is not None:
            yield from iter_json_ld_objects(graph)


def parse_json_ld(blocks: Iterable[str]) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for block in blocks:
        try:
            decoded = json.loads(block)
        except (json.JSONDecodeError, TypeError):
            continue
        objects.extend(iter_json_ld_objects(decoded))
    return objects


def schema_types(value: Any) -> set[str]:
    values = value if isinstance(value, list) else [value]
    return {str(item).rsplit("/", 1)[-1].casefold() for item in values if isinstance(item, str)}


def choose_media_schema(objects: Iterable[dict[str, Any]]) -> dict[str, Any]:
    preferred_types = {
        "movie",
        "tvseries",
        "creativeworkseries",
        "videoobject",
        "episode",
    }
    for item in objects:
        if schema_types(item.get("@type")) & preferred_types:
            return item
    return {}


def text_value(value: Any) -> str | None:
    if isinstance(value, str):
        normalized = " ".join(value.split())
        return normalized or None
    if isinstance(value, dict):
        return text_value(value.get("name"))
    return None


def names(value: Any) -> tuple[str, ...]:
    values = value if isinstance(value, list) else [value]
    return tuple(name for item in values if (name := text_value(item)) is not None)


def first_meta(meta: dict[str, str], *keys: str) -> str | None:
    return next((meta[key] for key in keys if key in meta), None)


def meta_names(
    meta_values: dict[str, list[str]],
    *keys: str,
) -> tuple[str, ...]:
    result: list[str] = []
    for key in keys:
        for value in meta_values.get(key, []):
            result.extend(
                item.strip() for item in NAME_SEPARATOR_PATTERN.split(value) if item.strip()
            )
    return tuple(result)


def image_url(value: Any) -> str | None:
    if isinstance(value, list):
        return next((url for item in value if (url := image_url(item))), None)
    if isinstance(value, dict):
        return text_value(value.get("url") or value.get("contentUrl"))
    return text_value(value)


def parse_date(value: Any) -> date | None:
    raw = text_value(value)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def parse_release_year(value: Any) -> int | None:
    raw = text_value(value)
    if not raw:
        return None
    match = YEAR_PATTERN.search(raw)
    return int(match.group(1)) if match else None


def parse_duration_minutes(value: Any) -> int | None:
    raw = text_value(value)
    if not raw:
        return None
    match = ISO_DURATION_PATTERN.fullmatch(raw)
    if not match:
        return None
    total_seconds = (
        int(match.group("hours") or 0) * 3600
        + int(match.group("minutes") or 0) * 60
        + int(match.group("seconds") or 0)
    )
    return max(1, round(total_seconds / 60)) if total_seconds else None


def parse_rating(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("ratingValue")
    try:
        rating = float(value)
    except (TypeError, ValueError):
        return None
    return rating if 0 <= rating <= 10 else None


def integer_value(value: Any) -> int | None:
    if isinstance(value, dict):
        value = value.get("value")
    if isinstance(value, int):
        return value
    raw = text_value(value)
    if not raw:
        return None
    match = re.search(r"\d+", raw)
    return int(match.group()) if match else None


def item_values(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    return tuple(value) if isinstance(value, list) else (value,)


def quality_value(value: Any) -> str | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return f"{int(value)}p"
    raw = text_value(value)
    if not raw:
        return None
    normalized = raw.strip()
    if normalized.isdigit():
        return f"{normalized}p"
    return normalized


def download_from_values(
    source_url: Any,
    *,
    base_url: str,
    resource_type: ParsedResourceType = ParsedResourceType.VIDEO,
    quality: Any = None,
    mime_type: Any = None,
    language: Any = None,
) -> ParsedDownload | None:
    raw_url = text_value(source_url)
    if not raw_url:
        return None
    absolute_url = urljoin(base_url, raw_url)
    if urlsplit(absolute_url).scheme not in {"http", "https"}:
        return None
    try:
        return ParsedDownload(
            source_url=absolute_url,
            quality=quality_value(quality),
            mime_type=text_value(mime_type),
            resource_type=resource_type,
            language=text_value(language),
        )
    except ValueError:
        return None


def deduplicate_downloads(
    downloads: Iterable[ParsedDownload | None],
) -> tuple[ParsedDownload, ...]:
    result: list[ParsedDownload] = []
    seen: set[tuple[ParsedResourceType, str]] = set()
    for download in downloads:
        if download is None:
            continue
        key = (download.resource_type, download.source_url)
        if key not in seen:
            seen.add(key)
            result.append(download)
    return tuple(result)


def schema_downloads(
    value: Any,
    *,
    base_url: str,
) -> tuple[ParsedDownload, ...]:
    downloads: list[ParsedDownload | None] = []
    for item in item_values(value):
        if isinstance(item, str):
            downloads.append(download_from_values(item, base_url=base_url))
            continue
        if not isinstance(item, dict):
            continue
        item_type = (
            ParsedResourceType.SUBTITLE
            if schema_types(item.get("@type")) & {"caption", "subtitle"}
            else ParsedResourceType.VIDEO
        )
        source_url = item.get("contentUrl")
        if source_url:
            downloads.append(
                download_from_values(
                    source_url,
                    base_url=base_url,
                    resource_type=item_type,
                    quality=(item.get("videoQuality") or item.get("quality") or item.get("height")),
                    mime_type=item.get("encodingFormat"),
                    language=item.get("inLanguage"),
                )
            )
        for nested_key in (
            "video",
            "associatedMedia",
            "encoding",
            "subtitle",
            "subtitles",
            "caption",
            "captions",
        ):
            if nested_key in item:
                downloads.extend(schema_downloads(item[nested_key], base_url=base_url))
    return deduplicate_downloads(downloads)


def html_downloads(
    document: WebPageMetadataParser,
    *,
    base_url: str,
) -> tuple[ParsedDownload, ...]:
    downloads: list[ParsedDownload | None] = []
    for element in document.media_elements:
        resource_type = ParsedResourceType(element["resource_type"])
        downloads.append(
            download_from_values(
                element.get("src"),
                base_url=base_url,
                resource_type=resource_type,
                quality=(
                    element.get("data-quality")
                    or element.get("label")
                    or element.get("res")
                    or element.get("height")
                ),
                mime_type=element.get("type"),
                language=element.get("srclang"),
            )
        )

    video_urls = (
        document.meta_values.get("og:video:secure_url", [])
        or document.meta_values.get("og:video", [])
        or document.meta_values.get("og:video:url", [])
    )
    qualities = document.meta_values.get("video:quality", []) or document.meta_values.get(
        "og:video:height", []
    )
    mime_types = document.meta_values.get("og:video:type", [])
    for index, source_url in enumerate(video_urls):
        downloads.append(
            download_from_values(
                source_url,
                base_url=base_url,
                quality=qualities[index] if index < len(qualities) else None,
                mime_type=mime_types[index] if index < len(mime_types) else None,
            )
        )

    subtitle_urls = (
        document.meta_values.get("subtitle", [])
        + document.meta_values.get("subtitles", [])
        + document.meta_values.get("video:subtitle", [])
    )
    for source_url in subtitle_urls:
        downloads.append(
            download_from_values(
                source_url,
                base_url=base_url,
                resource_type=ParsedResourceType.SUBTITLE,
            )
        )
    return deduplicate_downloads(downloads)


def episode_from_schema(
    value: Any,
    *,
    base_url: str,
    fallback_number: int,
) -> ParsedEpisode | None:
    if not isinstance(value, dict):
        return None
    episode_number = integer_value(value.get("episodeNumber")) or fallback_number
    title = text_value(value.get("name") or value.get("headline"))
    if not title:
        title = f"第 {episode_number} 集"
    thumbnail_url = image_url(value.get("image") or value.get("thumbnailUrl"))
    if thumbnail_url:
        thumbnail_url = urljoin(base_url, thumbnail_url)
    return ParsedEpisode(
        episode_number=episode_number,
        title=title,
        description=text_value(value.get("description")),
        air_date=parse_date(value.get("datePublished") or value.get("dateCreated")),
        duration_minutes=parse_duration_minutes(value.get("duration")),
        thumbnail_url=thumbnail_url,
        downloads=schema_downloads(value, base_url=base_url),
    )


def season_from_schema(
    value: Any,
    *,
    base_url: str,
    fallback_number: int,
) -> ParsedSeason | None:
    if not isinstance(value, dict):
        return None
    season_number = integer_value(value.get("seasonNumber")) or fallback_number
    episode_values = item_values(value.get("episode") or value.get("episodes"))
    episodes = tuple(
        episode
        for index, item in enumerate(episode_values, start=1)
        if (
            episode := episode_from_schema(
                item,
                base_url=base_url,
                fallback_number=index,
            )
        )
        is not None
    )
    poster_url = image_url(value.get("image") or value.get("thumbnailUrl"))
    if poster_url:
        poster_url = urljoin(base_url, poster_url)
    return ParsedSeason(
        season_number=season_number,
        episode_count=integer_value(value.get("numberOfEpisodes")) or len(episodes),
        title=text_value(value.get("name")),
        description=text_value(value.get("description")),
        poster_url=poster_url,
        air_date=parse_date(value.get("datePublished") or value.get("dateCreated")),
        episodes=episodes,
    )


def seasons_from_schema(
    schema: dict[str, Any],
    *,
    base_url: str,
) -> tuple[ParsedSeason, ...]:
    season_values = item_values(
        schema.get("containsSeason") or schema.get("season") or schema.get("seasons")
    )
    if not season_values and (schema.get("episode") or schema.get("episodes")):
        season_values = (
            {
                "@type": "TVSeason",
                "seasonNumber": schema.get("seasonNumber") or 1,
                "numberOfEpisodes": schema.get("numberOfEpisodes"),
                "episode": schema.get("episode") or schema.get("episodes"),
            },
        )
    return tuple(
        season
        for index, item in enumerate(season_values, start=1)
        if (
            season := season_from_schema(
                item,
                base_url=base_url,
                fallback_number=index,
            )
        )
        is not None
    )


def infer_media_type(schema: dict[str, Any], meta: dict[str, str]) -> ParsedMediaType:
    types = schema_types(schema.get("@type"))
    if types & {"tvseries", "creativeworkseries", "episode"}:
        return ParsedMediaType.SERIES
    if "movie" in types or meta.get("og:type", "").casefold() in {"video.movie", "movie"}:
        return ParsedMediaType.MOVIE
    return ParsedMediaType.OTHER


class GenericWebPageParser(ResourceParser):
    name = "generic-webpage"
    priority = -100
    supported_hosts = ()

    def __init__(self, fetcher: WebPageFetcher = fetch_web_page) -> None:
        self.fetcher = fetcher

    def supports(self, request: ParseRequest) -> bool:
        return urlsplit(request.source_url).scheme in {"http", "https"}

    async def parse(self, request: ParseRequest) -> ParseResult:
        response = await self.fetcher(request.source_url)
        document = WebPageMetadataParser()
        document.feed(response.text)
        schema = choose_media_schema(parse_json_ld(document.json_ld_blocks))
        meta = document.meta
        meta_values = document.meta_values

        title = (
            text_value(schema.get("name") or schema.get("headline"))
            or first_meta(
                meta,
                "og:title",
                "twitter:title",
                "title",
                "movie:title",
                "video:title",
                "name",
                "headline",
            )
            or document.title
        )
        if not title:
            raise ValueError("网页缺少可识别的标题")

        final_url = response.url
        canonical_url = (
            urljoin(final_url, document.canonical_url) if document.canonical_url else final_url
        )
        poster_url = image_url(schema.get("image") or schema.get("thumbnailUrl")) or first_meta(
            meta,
            "og:image",
            "og:image:url",
            "twitter:image",
            "twitter:image:src",
            "image",
            "thumbnail",
            "thumbnailurl",
        )
        if poster_url:
            poster_url = urljoin(final_url, poster_url)

        source_site = (
            meta.get("og:site_name") or text_value(schema.get("publisher")) or request.hostname
        )
        description = text_value(schema.get("description")) or first_meta(
            meta,
            "og:description",
            "twitter:description",
            "description",
            "movie:description",
            "video:description",
            "abstract",
        )
        release_value = (
            schema.get("datePublished")
            or schema.get("releaseDate")
            or schema.get("dateCreated")
            or first_meta(
                meta,
                "video:release_date",
                "movie:release_date",
                "release_date",
                "releasedate",
                "datepublished",
                "article:published_time",
                "date",
                "year",
            )
        )
        release_date = parse_date(release_value)
        release_year = release_date.year if release_date else parse_release_year(release_value)
        directors = names(schema.get("director")) + meta_names(
            meta_values,
            "director",
            "directors",
            "movie:director",
            "video:director",
        )
        actors = names(schema.get("actor") or schema.get("actors")) + meta_names(
            meta_values,
            "actor",
            "actors",
            "cast",
            "movie:actor",
            "video:actor",
        )
        genres = names(schema.get("genre"))
        if len(genres) == 1 and "," in genres[0]:
            genres = tuple(item.strip() for item in genres[0].split(","))
        downloads = deduplicate_downloads(
            (
                *schema_downloads(schema, base_url=final_url),
                *html_downloads(document, base_url=final_url),
            )
        )
        seasons = seasons_from_schema(schema, base_url=final_url)
        media_type = infer_media_type(schema, meta)
        if seasons:
            media_type = ParsedMediaType.SERIES

        return ParseResult(
            title=title,
            source_site=source_site,
            source_page_url=canonical_url,
            media_type=media_type,
            description=description,
            release_year=release_year,
            release_date=release_date,
            directors=directors,
            actors=actors,
            genres=genres,
            duration_minutes=parse_duration_minutes(schema.get("duration")),
            rating=parse_rating(schema.get("aggregateRating")),
            poster_url=poster_url,
            downloads=downloads,
            season_count=integer_value(schema.get("numberOfSeasons")) or len(seasons),
            seasons=seasons,
            extra={
                "parser": self.name,
                "json_ld_type": sorted(schema_types(schema.get("@type"))),
            },
        )
