from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from videocenter.models.download import DownloadStatus


class DownloadCreate(BaseModel):
    source_url: HttpUrl
    target_name: str = Field(min_length=1, max_length=255)
    media_id: int | None = None


class DownloadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    media_id: int | None
    source_url: str
    target_name: str
    status: DownloadStatus
    progress: float
    error_message: str | None
    created_at: datetime
    updated_at: datetime
