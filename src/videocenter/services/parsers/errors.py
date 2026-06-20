from typing import Any

from videocenter.core.exceptions import AppException, BadRequestError


class UnsupportedWebsiteError(BadRequestError):
    """Raised when no registered parser supports a resource website."""

    def __init__(
        self,
        source_url: str,
        hostname: str,
        supported_hosts: tuple[str, ...] = (),
    ) -> None:
        message = f"暂不支持网站：{hostname}" if hostname else "暂不支持该资源网站"
        super().__init__(
            message,
            code="UNSUPPORTED_WEBSITE",
            details={
                "hostname": hostname or None,
                "supported_hosts": list(supported_hosts),
            },
        )
        self.source_url = source_url
        self.hostname = hostname
        self.supported_hosts = supported_hosts


class ParserNotFoundError(UnsupportedWebsiteError):
    """Backward-compatible name used by R01-R03 callers."""


class ParseTimeoutError(AppException):
    def __init__(
        self,
        *,
        parser_name: str,
        hostname: str,
        attempts: int,
        timeout_seconds: float,
    ) -> None:
        super().__init__(
            "资源页面解析超时",
            code="PARSE_TIMEOUT",
            status_code=504,
            details={
                "parser": parser_name,
                "hostname": hostname,
                "attempts": attempts,
                "timeout_seconds": timeout_seconds,
            },
        )


class ParseFailedError(AppException):
    def __init__(
        self,
        *,
        parser_name: str,
        hostname: str,
        attempts: int,
        reason: str,
        details: Any = None,
    ) -> None:
        error_details = {
            "parser": parser_name,
            "hostname": hostname,
            "attempts": attempts,
            "reason": reason,
        }
        if details is not None:
            error_details["cause"] = details
        super().__init__(
            "资源页面解析失败",
            code="PARSE_FAILED",
            status_code=502,
            details=error_details,
        )
