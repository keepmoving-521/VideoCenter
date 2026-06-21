from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from videocenter.models.media import MediaType
from videocenter.schemas.common import ApiRequestModel, PositiveId


class HistoryUpsert(ApiRequestModel):
    media_id: PositiveId
    resource_id: PositiveId | None = None
    position_seconds: float = Field(ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_playback_position(self) -> "HistoryUpsert":
        if self.duration_seconds is not None and self.position_seconds > self.duration_seconds:
            raise ValueError("播放位置不能超过视频总时长")
        return self


class HistoryRead(HistoryUpsert):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_completed: bool
    completed_at: datetime | None
    watched_at: datetime


class PlaybackProgressUpdate(ApiRequestModel):
    position_seconds: float = Field(ge=0)
    duration_seconds: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_playback_position(self) -> "PlaybackProgressUpdate":
        if self.duration_seconds is not None and self.position_seconds > self.duration_seconds:
            raise ValueError("播放位置不能超过视频总时长")
        return self


class HistoryMediaSummary(BaseModel):
    id: int
    title: str
    media_type: MediaType
    release_year: int | None
    poster_url: str | None


class HistoryListItem(HistoryRead):
    media: HistoryMediaSummary


class HistoryPage(BaseModel):
    items: list[HistoryListItem]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool
