from pydantic import BaseModel

from videocenter.schemas.media import LocalResourceRead


class PlaybackResourceDetail(BaseModel):
    resource: LocalResourceRead
    playable: bool
    file_exists: bool
    stream_url: str
    head_url: str
    cover_url: str | None
    preview_urls: list[str]
    subtitles_url: str
    supports_range: bool
    cache_control: str


class PlaybackSubtitle(BaseModel):
    subtitle_id: str
    source: str
    format: str | None
    language: str | None
    title: str | None
    is_default: bool
    is_forced: bool
    access_url: str | None


class PlaybackSubtitleList(BaseModel):
    resource_id: int
    subtitles: list[PlaybackSubtitle]
