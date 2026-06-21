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
    supports_range: bool
    cache_control: str
