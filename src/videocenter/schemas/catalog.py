from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from videocenter.schemas.common import ApiRequestModel, PositiveId, ShortText


class TagCreate(ApiRequestModel):
    name: ShortText = Field(max_length=100)


class TagUpdate(ApiRequestModel):
    name: ShortText = Field(max_length=100)


class TagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime


class TagDetailRead(TagRead):
    media_count: int


class MediaTagsUpdate(ApiRequestModel):
    tag_ids: list[PositiveId] = Field(default_factory=list, max_length=100)

    @field_validator("tag_ids")
    @classmethod
    def deduplicate_tag_ids(cls, value: list[int]) -> list[int]:
        return list(dict.fromkeys(value))


class SeasonCreate(ApiRequestModel):
    season_number: int = Field(ge=0, le=10_000)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)
    poster_url: HttpUrl | None = None
    air_date: date | None = None

    def to_model_values(self) -> dict:
        values = self.model_dump()
        if values["poster_url"] is not None:
            values["poster_url"] = str(values["poster_url"])
        return values


class SeasonUpdate(ApiRequestModel):
    season_number: int | None = Field(default=None, ge=0, le=10_000)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)
    poster_url: HttpUrl | None = None
    air_date: date | None = None

    @model_validator(mode="after")
    def require_update_field(self) -> "SeasonUpdate":
        if not self.model_fields_set:
            raise ValueError("至少需要提供一个待更新字段")
        return self

    def to_model_values(self) -> dict:
        values = self.model_dump(exclude_unset=True)
        if "poster_url" in values and values["poster_url"] is not None:
            values["poster_url"] = str(values["poster_url"])
        return values


class SeasonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    media_id: int
    season_number: int
    title: str | None
    description: str | None
    poster_url: str | None
    air_date: date | None
    created_at: datetime
    updated_at: datetime


class EpisodeCreate(ApiRequestModel):
    episode_number: int = Field(gt=0, le=100_000)
    title: ShortText
    description: str | None = Field(default=None, max_length=10_000)
    air_date: date | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=100_000)
    thumbnail_url: HttpUrl | None = None

    def to_model_values(self) -> dict:
        values = self.model_dump()
        if values["thumbnail_url"] is not None:
            values["thumbnail_url"] = str(values["thumbnail_url"])
        return values


class EpisodeUpdate(ApiRequestModel):
    episode_number: int | None = Field(default=None, gt=0, le=100_000)
    title: ShortText | None = None
    description: str | None = Field(default=None, max_length=10_000)
    air_date: date | None = None
    duration_minutes: int | None = Field(default=None, gt=0, le=100_000)
    thumbnail_url: HttpUrl | None = None

    @field_validator("title")
    @classmethod
    def reject_null_title(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("分集标题不能设置为空")
        return value

    @model_validator(mode="after")
    def require_update_field(self) -> "EpisodeUpdate":
        if not self.model_fields_set:
            raise ValueError("至少需要提供一个待更新字段")
        return self

    def to_model_values(self) -> dict:
        values = self.model_dump(exclude_unset=True)
        if "thumbnail_url" in values and values["thumbnail_url"] is not None:
            values["thumbnail_url"] = str(values["thumbnail_url"])
        return values


class EpisodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season_id: int
    episode_number: int
    title: str
    description: str | None
    air_date: date | None
    duration_minutes: int | None
    thumbnail_url: str | None
    created_at: datetime
    updated_at: datetime


class SeasonWithEpisodesRead(SeasonRead):
    episodes: list[EpisodeRead] = Field(default_factory=list)


class EpisodeDetailRead(EpisodeRead):
    media_id: int
    season_number: int


class MediaHierarchyRead(BaseModel):
    media_id: int
    title: str
    seasons: list[SeasonWithEpisodesRead] = Field(default_factory=list)
