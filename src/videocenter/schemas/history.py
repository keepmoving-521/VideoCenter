from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from videocenter.models.media import MediaType
from videocenter.schemas.common import ApiRequestModel, PositiveId


class HistoryUpsert(ApiRequestModel):
    media_id: PositiveId
    resource_id: PositiveId | None = None
    episode_id: PositiveId | None = None
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
    episode_id: PositiveId | None = None
    position_seconds: float = Field(ge=0)
    duration_seconds: float | None = Field(default=None, gt=0)
    watched_seconds: float | None = Field(default=None, ge=0, le=86_400)

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


class WatchedEpisodeRead(BaseModel):
    id: int
    media_id: int
    season_id: int
    season_number: int
    episode_number: int
    title: str
    thumbnail_url: str | None
    resource_id: int | None
    stream_url: str | None
    position_seconds: float
    duration_seconds: float | None
    is_completed: bool
    watched_at: datetime


class NextEpisodeRead(BaseModel):
    media_id: int
    current_episode_id: int
    id: int
    season_id: int
    season_number: int
    episode_number: int
    title: str
    description: str | None
    duration_minutes: int | None
    thumbnail_url: str | None
    resource_id: int | None
    playable: bool
    stream_url: str | None


class HistoryBatchDeleteRequest(ApiRequestModel):
    media_ids: list[PositiveId] = Field(min_length=1, max_length=100)

    @field_validator("media_ids")
    @classmethod
    def deduplicate_media_ids(cls, value: list[int]) -> list[int]:
        return list(dict.fromkeys(value))


class HistoryBatchDeleteResponse(BaseModel):
    deleted_count: int
    deleted_media_ids: list[int]
    missing_media_ids: list[int]


class HistoryClearResponse(BaseModel):
    deleted_count: int


class WatchStatsSummary(BaseModel):
    total_watched_seconds: float
    total_watched_minutes: float
    total_watched_hours: float
    watched_media_count: int
    active_days: int
    average_daily_seconds: float
    completed_count: int


class DailyWatchStatRead(BaseModel):
    date: date
    watched_seconds: float
    watched_minutes: float
    watched_media_count: int
    completed_count: int


class DailyWatchStatsResponse(BaseModel):
    start_date: date
    end_date: date
    items: list[DailyWatchStatRead]
