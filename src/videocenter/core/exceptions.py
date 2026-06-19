from typing import Any


class AppException(Exception):
    """Base exception for errors that are safe to expose to API clients."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "APPLICATION_ERROR",
        status_code: int = 400,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        self.headers = headers


class BadRequestError(AppException):
    def __init__(
        self,
        message: str = "请求参数不正确",
        *,
        code: str = "BAD_REQUEST",
        details: Any = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            status_code=400,
            details=details,
        )


class NotFoundError(AppException):
    def __init__(
        self,
        message: str = "请求的资源不存在",
        *,
        code: str = "RESOURCE_NOT_FOUND",
        details: Any = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            status_code=404,
            details=details,
        )


class ConflictError(AppException):
    def __init__(
        self,
        message: str = "资源状态冲突",
        *,
        code: str = "RESOURCE_CONFLICT",
        details: Any = None,
    ) -> None:
        super().__init__(
            message,
            code=code,
            status_code=409,
            details=details,
        )
