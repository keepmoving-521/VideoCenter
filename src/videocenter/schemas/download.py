import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from videocenter.models.download import DownloadStatus
from videocenter.schemas.common import ApiRequestModel, PositiveId

INVALID_FILE_NAME_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class DownloadCreate(ApiRequestModel):
    source_url: HttpUrl
    target_name: str | None = Field(default=None, min_length=1, max_length=512)
    media_id: PositiveId | None = None
    priority: int = Field(default=0, ge=-100, le=100)

    @field_validator("target_name")
    @classmethod
    def validate_target_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if INVALID_FILE_NAME_PATTERN.search(value):
            raise ValueError("目标文件名包含非法字符")
        if value.endswith((".", " ")):
            raise ValueError("目标文件名不能以点或空格结尾")
        return value


class DownloadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    media_id: int | None
    source_url: str
    target_name: str
    status: DownloadStatus
    priority: int
    progress: float
    downloaded_bytes: int
    total_bytes: int | None
    speed_bytes_per_second: float | None
    remaining_seconds: float | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
