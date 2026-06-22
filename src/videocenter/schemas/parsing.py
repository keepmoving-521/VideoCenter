from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

from videocenter.schemas.common import ApiRequestModel
from videocenter.services.parsers import ParseResult


class ParsePreviewRequest(ApiRequestModel):
    source_url: HttpUrl
    preferred_language: str | None = Field(default=None, max_length=50)


class ParsePreviewResponse(BaseModel):
    parse_task_id: str
    background_task_id: int
    preview_id: str
    expires_at: datetime
    result: ParseResult


class ParseConfirmRequest(ApiRequestModel):
    preview_id: str = Field(min_length=32, max_length=64)
    result: ParseResult


class ParseConfirmResponse(BaseModel):
    confirmation_id: str
    expires_at: datetime
    result: ParseResult


class ParseSaveRequest(ApiRequestModel):
    confirmation_id: str = Field(min_length=32, max_length=64)


class ParseSaveResponse(BaseModel):
    media_id: int
    title: str
    tags_created: int
    seasons_created: int
    episodes_created: int
    downloads_detected: int
    subtitles_detected: int
