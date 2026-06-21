from datetime import date, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)

from videocenter.models.media import MediaStatus, MediaType
from videocenter.schemas.catalog import SeasonWithEpisodesRead, TagRead
from videocenter.schemas.common import ApiRequestModel, PositiveId, ShortText

OptionalShortText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
ContentRating = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=32),
]


class MediaSortField(StrEnum):
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    TITLE = "title"
    RELEASE_YEAR = "release_year"
    RATING = "rating"
    PERSONAL_RATING = "personal_rating"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


def normalize_string_list(
    values: list[str],
    *,
    field_label: str,
    item_max_length: int = 255,
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{field_label}不能为空")
        if len(stripped) > item_max_length:
            raise ValueError(f"{field_label}长度不能超过 {item_max_length} 个字符")
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
    status: MediaStatus = MediaStatus.PENDING
    description: str | None = Field(default=None, max_length=10_000)
    release_year: int | None = Field(default=None, ge=1888, le=2100)
    release_date: date | None = None
    content_rating: ContentRating | None = None
    source_site: OptionalShortText | None = Field(default=None, max_length=100)
    source_page_url: HttpUrl | None = Field(
        default=None,
        validation_alias=AliasChoices("source_page_url", "source_url"),
    )
    directors: list[str] = Field(default_factory=list, max_length=100)
    actors: list[str] = Field(default_factory=list, max_length=500)
    regions: list[str] = Field(default_factory=list, max_length=50)
    languages: list[str] = Field(default_factory=list, max_length=50)
    genres: list[str] = Field(default_factory=list, max_length=50)
    duration_minutes: int | None = Field(default=None, gt=0, le=100_000)
    rating: float | None = Field(default=None, ge=0, le=10)
    is_favorite: bool = False
    personal_rating: float | None = Field(default=None, ge=0, le=10)
    personal_notes: str | None = Field(default=None, max_length=10_000)
    poster_url: HttpUrl | None = None
    background_url: HttpUrl | None = None

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("personal_notes")
    @classmethod
    def normalize_personal_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("alternative_titles")
    @classmethod
    def validate_alternative_titles(cls, value: list[str]) -> list[str]:
        return normalize_string_list(value, field_label="影视别名")

    @field_validator("directors")
    @classmethod
    def validate_directors(cls, value: list[str]) -> list[str]:
        return normalize_string_list(value, field_label="导演")

    @field_validator("actors")
    @classmethod
    def validate_actors(cls, value: list[str]) -> list[str]:
        return normalize_string_list(value, field_label="演员")

    @field_validator("regions")
    @classmethod
    def validate_regions(cls, value: list[str]) -> list[str]:
        return normalize_string_list(value, field_label="地区", item_max_length=100)

    @field_validator("languages")
    @classmethod
    def validate_languages(cls, value: list[str]) -> list[str]:
        return normalize_string_list(value, field_label="语言", item_max_length=100)

    @field_validator("genres")
    @classmethod
    def validate_genres(cls, value: list[str]) -> list[str]:
        return normalize_string_list(value, field_label="类别", item_max_length=100)

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
        for field in ("poster_url", "background_url", "source_page_url"):
            if values[field] is not None:
                values[field] = str(values[field])
        return values


class MediaUpdate(ApiRequestModel):
    title: ShortText | None = None
    sort_title: OptionalShortText | None = None
    original_title: OptionalShortText | None = None
    alternative_titles: list[str] | None = Field(default=None, max_length=50)
    media_type: MediaType | None = None
    status: MediaStatus | None = None
    description: str | None = Field(default=None, max_length=10_000)
    release_year: int | None = Field(default=None, ge=1888, le=2100)
    release_date: date | None = None
    content_rating: ContentRating | None = None
    source_site: OptionalShortText | None = Field(default=None, max_length=100)
    source_page_url: HttpUrl | None = Field(
        default=None,
        validation_alias=AliasChoices("source_page_url", "source_url"),
    )
    directors: list[str] | None = Field(default=None, max_length=100)
    actors: list[str] | None = Field(default=None, max_length=500)
    regions: list[str] | None = Field(default=None, max_length=50)
    languages: list[str] | None = Field(default=None, max_length=50)
    genres: list[str] | None = Field(default=None, max_length=50)
    duration_minutes: int | None = Field(default=None, gt=0, le=100_000)
    rating: float | None = Field(default=None, ge=0, le=10)
    is_favorite: bool | None = None
    personal_rating: float | None = Field(default=None, ge=0, le=10)
    personal_notes: str | None = Field(default=None, max_length=10_000)
    poster_url: HttpUrl | None = None
    background_url: HttpUrl | None = None

    @field_validator(
        "title",
        "media_type",
        "status",
        "alternative_titles",
        "directors",
        "actors",
        "regions",
        "languages",
        "genres",
        "is_favorite",
    )
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

    @field_validator("personal_notes")
    @classmethod
    def normalize_personal_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("alternative_titles")
    @classmethod
    def validate_alternative_titles(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return normalize_string_list(value, field_label="影视别名")

    @field_validator("directors")
    @classmethod
    def validate_directors(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else normalize_string_list(value, field_label="导演")

    @field_validator("actors")
    @classmethod
    def validate_actors(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else normalize_string_list(value, field_label="演员")

    @field_validator("regions", "languages", "genres")
    @classmethod
    def validate_classification_lists(
        cls,
        value: list[str] | None,
        info,
    ) -> list[str] | None:
        if value is None:
            return None
        labels = {"regions": "地区", "languages": "语言", "genres": "类别"}
        return normalize_string_list(
            value,
            field_label=labels[info.field_name],
            item_max_length=100,
        )

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
        for field in ("poster_url", "background_url", "source_page_url"):
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
    modified_at_ns: int | None
    created_at: datetime


class MediaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    sort_title: str | None
    original_title: str | None
    alternative_titles: list[str]
    media_type: MediaType
    status: MediaStatus
    description: str | None
    release_year: int | None
    release_date: date | None
    content_rating: str | None
    source_site: str | None
    source_page_url: str | None
    directors: list[str]
    actors: list[str]
    regions: list[str]
    languages: list[str]
    genres: list[str]
    duration_minutes: int | None
    rating: float | None
    is_favorite: bool
    personal_rating: float | None
    personal_notes: str | None
    poster_url: str | None
    background_url: str | None
    created_at: datetime
    updated_at: datetime
    resources: list[LocalResourceRead] = Field(default_factory=list)
    tags: list[TagRead] = Field(default_factory=list)


class MediaPage(BaseModel):
    items: list[MediaRead]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


class MediaDetailRead(MediaRead):
    seasons: list[SeasonWithEpisodesRead] = Field(default_factory=list)


class MediaBatchDeleteRequest(ApiRequestModel):
    media_ids: list[PositiveId] = Field(min_length=1, max_length=100)

    @field_validator("media_ids")
    @classmethod
    def deduplicate_media_ids(cls, value: list[int]) -> list[int]:
        return list(dict.fromkeys(value))


class MediaBatchDeleteResponse(BaseModel):
    deleted_count: int
    deleted_ids: list[int]
    missing_ids: list[int]


class MediaFavoriteRead(BaseModel):
    media_id: int
    is_favorite: bool


class DuplicateMediaItem(BaseModel):
    id: int
    title: str
    media_type: MediaType
    release_year: int | None
    source_site: str | None
    source_page_url: str | None


class DuplicateMediaGroup(BaseModel):
    reasons: list[str]
    items: list[DuplicateMediaItem]


class MediaDuplicatesResponse(BaseModel):
    group_count: int
    duplicate_media_count: int
    groups: list[DuplicateMediaGroup]


class MediaMergeRequest(ApiRequestModel):
    target_media_id: PositiveId
    source_media_ids: list[PositiveId] = Field(min_length=1, max_length=100)

    @field_validator("source_media_ids")
    @classmethod
    def deduplicate_source_ids(cls, value: list[int]) -> list[int]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def reject_target_as_source(self) -> "MediaMergeRequest":
        if self.target_media_id in self.source_media_ids:
            raise ValueError("目标影视不能同时作为待合并影视")
        return self


class MediaMergeResponse(BaseModel):
    target_media_id: int
    merged_media_ids: list[int]
    moved_local_resources: int
    moved_download_tasks: int
    merged_tags: int
    merged_seasons: int
    merged_episodes: int
    merged_watch_history: bool


class MediaLibraryStats(BaseModel):
    total_media: int
    favorite_media: int
    media_with_local_resources: int
    total_local_resources: int
    total_download_tasks: int
    total_tags: int
    total_seasons: int
    total_episodes: int
    by_type: dict[str, int]
    by_status: dict[str, int]


class LocalScanRequest(ApiRequestModel):
    path: str | None = Field(default=None, min_length=1, max_length=2048)
    media_id: PositiveId | None = None
    incremental: bool = True

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str | None) -> str | None:
        if value is not None and "\x00" in value:
            raise ValueError("扫描路径不能包含空字符")
        return value
