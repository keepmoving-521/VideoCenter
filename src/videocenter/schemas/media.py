from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from videocenter.models.media import MediaType


class MediaCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    original_title: str | None = Field(default=None, max_length=255)
    media_type: MediaType = MediaType.MOVIE
    description: str | None = None
    release_year: int | None = Field(default=None, ge=1888, le=2100)
    poster_url: HttpUrl | None = None
    source_url: HttpUrl | None = None


class MediaUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    original_title: str | None = Field(default=None, max_length=255)
    media_type: MediaType | None = None
    description: str | None = None
    release_year: int | None = Field(default=None, ge=1888, le=2100)
    poster_url: HttpUrl | None = None
    source_url: HttpUrl | None = None


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


class LocalScanRequest(BaseModel):
    path: str | None = None
    media_id: int | None = None


class LocalScanResult(BaseModel):
    scanned: int
    added: int
    updated: int
