import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from videocenter.models.media import MediaType

_SERIES_PATTERNS = (
    re.compile(
        r"(?ix)(?P<title>.*?)(?:[\s._-]+)?"
        r"S(?P<season>\d{1,2})[\s._-]*E(?P<episode>\d{1,3})(?:\b|(?=[\s._-]))"
    ),
    re.compile(
        r"(?ix)(?P<title>.*?)(?:[\s._-]+)?"
        r"(?P<season>\d{1,2})x(?P<episode>\d{1,3})(?:\b|(?=[\s._-]))"
    ),
    re.compile(
        r"(?i)(?P<title>.*?)"
        r"第\s*(?P<season>\d{1,2})\s*季[\s._-]*"
        r"第\s*(?P<episode>\d{1,3})\s*[集话話]"
    ),
)
_YEAR_PATTERN = re.compile(r"(?<!\d)(?P<year>18(?:8[8-9]|9\d)|19\d{2}|20\d{2}|2100)(?!\d)")
_TECHNICAL_SUFFIX = re.compile(
    r"(?ix)(?:^|[\s._-])(?:"
    r"4320p|2160p|1080[pi]|720p|576p|480p|4k|8k|"
    r"uhd|hdr10\+?|hdr|dolby[\s._-]*vision|dv|"
    r"blu[\s._-]*ray|bdrip|brrip|web[\s._-]*dl|webrip|hdtv|dvdrip|remux|"
    r"x26[45]|h[\s._-]*26[45]|hevc|av1|10bit|"
    r"aac|ac3|eac3|dts(?:[\s._-]*hd)?|truehd|atmos"
    r")(?:$|[\s._-])"
)
_TRAILING_BRACKETS = re.compile(r"(?:\s*[\[(][^\])]*[\])])+\s*$")
_SEPARATORS = re.compile(r"[\s._-]+")


@dataclass(frozen=True, slots=True)
class ParsedVideoFilename:
    title: str
    media_type: MediaType
    release_year: int | None = None
    season_number: int | None = None
    episode_number: int | None = None


def parse_video_filename(file_name: str) -> ParsedVideoFilename:
    """Extract stable media metadata from a video file name."""
    stem = unicodedata.normalize("NFKC", Path(file_name).stem).strip()
    year_match = _YEAR_PATTERN.search(stem)
    release_year = int(year_match.group("year")) if year_match else None

    for pattern in _SERIES_PATTERNS:
        match = pattern.search(stem)
        if match is None:
            continue
        return ParsedVideoFilename(
            title=_clean_title(match.group("title"), fallback=stem),
            media_type=MediaType.SERIES,
            release_year=release_year,
            season_number=int(match.group("season")),
            episode_number=int(match.group("episode")),
        )

    title_end = len(stem)
    if year_match is not None:
        title_end = min(title_end, year_match.start())
    technical_match = _TECHNICAL_SUFFIX.search(stem)
    if technical_match is not None:
        title_end = min(title_end, technical_match.start())

    return ParsedVideoFilename(
        title=_clean_title(stem[:title_end], fallback=stem),
        media_type=MediaType.MOVIE,
        release_year=release_year,
    )


def _clean_title(value: str, *, fallback: str) -> str:
    value = _TRAILING_BRACKETS.sub("", value)
    cleaned = _SEPARATORS.sub(" ", value).strip(" []()")
    if cleaned:
        return cleaned
    fallback_cleaned = _SEPARATORS.sub(" ", fallback).strip(" []()")
    return fallback_cleaned or "Unknown"
