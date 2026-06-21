from datetime import datetime

from pydantic import ConfigDict, Field, model_validator

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
    watched_at: datetime


class PlaybackProgressUpdate(ApiRequestModel):
    position_seconds: float = Field(ge=0)
    duration_seconds: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_playback_position(self) -> "PlaybackProgressUpdate":
        if self.duration_seconds is not None and self.position_seconds > self.duration_seconds:
            raise ValueError("播放位置不能超过视频总时长")
        return self
