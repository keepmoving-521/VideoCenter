from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from videocenter.schemas.common import ApiRequestModel, ShortText


class MediaDirectoryCreate(ApiRequestModel):
    name: ShortText = Field(max_length=100)
    path: str = Field(min_length=1, max_length=2048)
    is_default: bool = False
    is_enabled: bool = True
    auto_scan: bool = True

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("媒体目录路径不能包含空字符")
        return value


class MediaDirectoryUpdate(ApiRequestModel):
    name: ShortText | None = Field(default=None, max_length=100)
    path: str | None = Field(default=None, min_length=1, max_length=2048)
    is_default: bool | None = None
    is_enabled: bool | None = None
    auto_scan: bool | None = None

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str | None) -> str | None:
        if value is not None and "\x00" in value:
            raise ValueError("媒体目录路径不能包含空字符")
        return value

    @field_validator("name", "is_default", "is_enabled", "auto_scan")
    @classmethod
    def reject_null_values(cls, value):
        if value is None:
            raise ValueError("该字段不能设置为空")
        return value

    @model_validator(mode="after")
    def require_update_field(self) -> "MediaDirectoryUpdate":
        if not self.model_fields_set:
            raise ValueError("至少需要提供一个待更新字段")
        return self


class MediaDirectoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    path: str
    is_default: bool
    is_enabled: bool
    auto_scan: bool
    created_at: datetime
    updated_at: datetime
