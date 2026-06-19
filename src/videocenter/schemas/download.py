import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl, field_validator

from videocenter.models.download import DownloadStatus
from videocenter.schemas.common import ApiRequestModel, PositiveId, ShortText

INVALID_FILE_NAME_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class DownloadCreate(ApiRequestModel):
    source_url: HttpUrl
    target_name: ShortText
    media_id: PositiveId | None = None

    @field_validator("target_name")
    @classmethod
    def validate_target_name(cls, value: str) -> str:
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
    progress: float
    error_message: str | None
    created_at: datetime
    updated_at: datetime
