from pydantic import BaseModel


class MediaToolStatus(BaseModel):
    name: str
    available: bool
    configured_path: str | None
    executable_path: str | None
    version: str | None
    error: str | None


class MediaToolsStatus(BaseModel):
    available: bool
    ffmpeg: MediaToolStatus
    ffprobe: MediaToolStatus
