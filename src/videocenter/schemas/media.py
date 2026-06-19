from datetime import date, datetime
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
ContentRating = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=32),
]


def normalize_alternative_titles(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        stripped = value.strip()
        if not stripped:
            raise ValueError("影视别名不能为空")
        if len(stripped) > 255:
            raise ValueError("影视别名长度不能超过 255 个字符")
        comparison_key = stripped.casefold()
        if comparison_key not in seen:
            seen.add(comparison_key)
            normalized.append(stripped)
    return normalized


class MediaCreate(ApiRequestModel):
    title: ShortText
    sort_title: OptionalShortText | None = None
    original_title: OptionalShortText | None = None
    alternative_titles: list[str] = Field(default_factory=list, max_length=50)
    media_type: MediaType = MediaType.MOVIE
    description: str | None = Field(default=None, max_length=10_000)
    release_year: int | None = Field(default=None, ge=1888, le=2100)
    release_date: date | None = None
    content_rating: ContentRating | None = None
    poster_url: HttpUrl | None = None
    source_url: HttpUrl | None = None

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("alternative_titles")
    @classmethod
    def validate_alternative_titles(cls, value: list[str]) -> list[str]:
        return normalize_alternative_titles(value)

    @model_validator(mode="after")
    def synchronize_release_year(self) -> "MediaCreate":
        if self.release_date is None:
            return self
        if self.release_year is not None and self.release_year != self.release_date.year:
            raise ValueError("上映年份必须与上映日期的年份一致")
        self.release_year = self.release_date.year
        return self

    def to_model_values(self) -> dict:
        values = self.model_dump()
        for field in ("poster_url", "source_url"):
            if values[field] is not None:
                values[field] = str(values[field])
        return values


class MediaUpdate(ApiRequestModel):
    title: ShortText | None = None
    sort_title: OptionalShortText | None = None
    original_title: OptionalShortText | None = None
    alternative_titles: list[str] | None = Field(default=None, max_length=50)
    media_type: MediaType | None = None
    description: str | None = Field(default=None, max_length=10_000)
    release_year: int | None = Field(default=None, ge=1888, le=2100)
    release_date: date | None = None
    content_rating: ContentRating | None = None
    poster_url: HttpUrl | None = None
    source_url: HttpUrl | None = None

    @field_validator("title", "media_type", "alternative_titles")
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

    @field_validator("alternative_titles")
    @classmethod
    def validate_alternative_titles(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return normalize_alternative_titles(value)

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "MediaUpdate":
        if not self.model_fields_set:
            raise ValueError("至少需要提供一个待更新字段")
        if self.release_date is not None:
            if self.release_year is not None and self.release_year != self.release_date.year:
                raise ValueError("上映年份必须与上映日期的年份一致")
            self.release_year = self.release_date.year
        return self

    def to_model_values(self) -> dict:
        values = self.model_dump(exclude_unset=True)
        for field in ("poster_url", "source_url"):
            if field in values and values[field] is not None:
                values[field] = str(values[field])
        return values


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
    sort_title: str | None
    original_title: str | None
    alternative_titles: list[str]
    media_type: MediaType
    description: str | None
    release_year: int | None
    release_date: date | None
    content_rating: str | None
    poster_url: str | None
    source_url: str | None
    created_at: datetime
    updated_at: datetime
    resources: list[LocalResourceRead] = Field(default_factory=list)


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
