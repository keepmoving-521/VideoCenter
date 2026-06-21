from pydantic import BaseModel

from videocenter.schemas.media import AudioTrackRead, LocalResourceRead
from videocenter.services.playback_capabilities import BrowserSupportStatus


class PlaybackResourceDetail(BaseModel):
    resource: LocalResourceRead
    playable: bool
    file_exists: bool
    stream_url: str
    head_url: str
    cover_url: str | None
    preview_urls: list[str]
    subtitles_url: str
    audio_tracks_url: str
    quality_url: str
    compatibility_url: str
    hls_task_create_url: str
    progress_url: str
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


class PlaybackAudioTrackList(BaseModel):
    resource_id: int
    default_stream_index: int | None
    tracks: list[AudioTrackRead]


class PlaybackVideoQuality(BaseModel):
    resource_id: int
    label: str | None
    width: int | None
    height: int | None
    aspect_ratio: str | None
    pixel_count: int | None
    bitrate: int | None
    video_codec: str | None


class PlaybackBrowserCompatibility(BaseModel):
    resource_id: int
    browser_family: str
    container: str | None
    mime_type: str
    video_codec: str | None
    audio_codec: str | None
    status: BrowserSupportStatus
    direct_play: bool
    can_play_type: str
    reason: str
    recommended_action: str
