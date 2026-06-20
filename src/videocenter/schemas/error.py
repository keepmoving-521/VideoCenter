from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(examples=["MEDIA_NOT_FOUND"])
    message: str = Field(examples=["影视条目不存在"])
    details: Any = None


class ErrorMeta(BaseModel):
    request_id: str
    timestamp: datetime
    path: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
    meta: ErrorMeta


STANDARD_ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "请求参数或业务请求错误"},
    404: {"model": ErrorResponse, "description": "请求的资源不存在"},
    409: {"model": ErrorResponse, "description": "资源状态冲突"},
    422: {"model": ErrorResponse, "description": "请求参数校验失败"},
    500: {"model": ErrorResponse, "description": "服务器内部错误"},
    502: {"model": ErrorResponse, "description": "上游资源页面解析失败"},
    504: {"model": ErrorResponse, "description": "上游资源页面解析超时"},
}
