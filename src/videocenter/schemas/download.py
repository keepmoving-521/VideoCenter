import re
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from videocenter.models.download import DownloadStatus
from videocenter.schemas.common import ApiRequestModel, PositiveId

INVALID_FILE_NAME_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class DownloadProvider(StrEnum):
    AUTO = "auto"
    HTTP_DIRECT = "http-direct"
    YT_DLP = "yt-dlp"


class DownloadCreate(ApiRequestModel):
    source_url: HttpUrl
    target_name: str | None = Field(default=None, min_length=1, max_length=512)
    target_directory: str | None = Field(default=None, max_length=1024)
    expected_sha256: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-fA-F]{64}$",
    )
    media_id: PositiveId | None = None
    priority: int = Field(default=0, ge=-100, le=100)
    downloader: DownloadProvider = DownloadProvider.AUTO

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

    @field_validator("target_directory")
    @classmethod
    def validate_target_directory(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if "\x00" in value:
            raise ValueError("目标目录不能包含空字符")
        return value or None

    @field_validator("expected_sha256")
    @classmethod
    def normalize_expected_sha256(cls, value: str | None) -> str | None:
        return value.casefold() if value is not None else None


class DownloadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    media_id: int | None
    source_url: str
    target_name: str
    target_directory: str
    target_path: str | None
    downloader_name: str
    expected_sha256: str | None
    checksum_sha256: str | None
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
