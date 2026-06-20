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
    ParsedMediaType,
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

        return ParseResult(
            title=title,
            source_site=source_site,
            source_page_url=canonical_url,
            media_type=infer_media_type(schema, meta),
            description=description,
            release_year=release_year,
            release_date=release_date,
            directors=directors,
            actors=actors,
            genres=genres,
            duration_minutes=parse_duration_minutes(schema.get("duration")),
            rating=parse_rating(schema.get("aggregateRating")),
            poster_url=poster_url,
            extra={
                "parser": self.name,
                "json_ld_type": sorted(schema_types(schema.get("@type"))),
            },
        )
