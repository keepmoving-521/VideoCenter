from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)

from videocenter.models.media import MediaType
from videocenter.schemas.common import ApiRequestModel, PositiveId, ShortText

OptionalShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class MediaCreate(ApiRequestModel):
    title: ShortText
    original_title: OptionalShortText | None = None
    media_type: MediaType = MediaType.MOVIE
    description: str | None = Field(default=None, max_length=10_000)
    release_year: int | None = Field(default=None, ge=1888, le=2100)
    poster_url: HttpUrl | None = None
    source_url: HttpUrl | None = None

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class MediaUpdate(ApiRequestModel):
    title: ShortText | None = None
    original_title: OptionalShortText | None = None
    media_type: MediaType | None = None
    description: str | None = Field(default=None, max_length=10_000)
    release_year: int | None = Field(default=None, ge=1888, le=2100)
    poster_url: HttpUrl | None = None
    source_url: HttpUrl | None = None

    @field_validator("title", "media_type")
    @classmethod
    def reject_required_field_nulls(cls, value):
        if value is None:
            raise ValueError("该字段不能设置为空")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "MediaUpdate":
        if not self.model_fields_set:
            raise ValueError("至少需要提供一个待更新字段")
        return self


class LocalResourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    media_id: int | None
    file_name: str
    file_size: int
    mime_type: str
    duration_seconds: float | None
    created_at: datetime


class MediaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    original_title: str | None
    media_type: MediaType
    description: str | None
    release_year: int | None
    poster_url: str | None
    source_url: str | None
    created_at: datetime
    updated_at: datetime
    resources: list[LocalResourceRead] = []


class LocalScanRequest(ApiRequestModel):
    path: str | None = Field(default=None, min_length=1, max_length=2048)
    media_id: PositiveId | None = None

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str | None) -> str | None:
        if value is not None and "\x00" in value:
            raise ValueError("扫描路径不能包含空字符")
        return value


class LocalScanResult(BaseModel):
    scanned: int
    added: int
    updated: int
