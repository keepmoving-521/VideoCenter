from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from enum import StrEnum
from pathlib import Path
from threading import Event
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DownloaderDataModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


def normalize_download_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("下载地址必须是有效的 HTTP 或 HTTPS 地址")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("下载地址不能包含用户名或密码")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("下载地址端口无效") from exc

    scheme = parsed.scheme.casefold()
    host = parsed.hostname.encode("idna").decode("ascii").casefold()
    display_host = f"[{host}]" if ":" in host else host
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = display_host if port is None or default_port else f"{display_host}:{port}"
    return urlunsplit((scheme, netloc, parsed.path or "/", parsed.query, ""))


class DownloadRequest(DownloaderDataModel):
    source_url: str
    target_path: Path
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = Field(default=30, gt=0, le=3600)
    chunk_size: int = Field(default=1024 * 1024, ge=1024, le=64 * 1024 * 1024)
    overwrite: bool = False
    expected_sha256: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-fA-F]{64}$",
    )

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        return normalize_download_url(value)

    @field_validator("target_path")
    @classmethod
    def validate_target_path(cls, value: Path) -> Path:
        if not value.name or value.name in {".", ".."}:
            raise ValueError("下载目标必须包含文件名")
        return value

    @field_validator("headers")
    @classmethod
    def validate_headers(cls, value: Mapping[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for name, header_value in value.items():
            normalized_name = name.strip()
            normalized_value = header_value.strip()
            if not normalized_name or "\r" in normalized_name or "\n" in normalized_name:
                raise ValueError("请求头名称无效")
            if "\r" in normalized_value or "\n" in normalized_value:
                raise ValueError("请求头内容不能包含换行符")
            normalized[normalized_name] = normalized_value
        return normalized

    @field_validator("expected_sha256")
    @classmethod
    def normalize_expected_sha256(cls, value: str | None) -> str | None:
        return value.casefold() if value is not None else None

    @property
    def scheme(self) -> str:
        return urlsplit(self.source_url).scheme

    @property
    def hostname(self) -> str:
        return urlsplit(self.source_url).hostname or ""


class DownloadProgressState(StrEnum):
    STARTING = "starting"
    DOWNLOADING = "downloading"
    FINALIZING = "finalizing"


class DownloadProgress(DownloaderDataModel):
    state: DownloadProgressState
    downloaded_bytes: int = Field(default=0, ge=0)
    total_bytes: int | None = Field(default=None, gt=0)
    speed_bytes_per_second: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_downloaded_bytes(self) -> "DownloadProgress":
        if self.total_bytes is not None and self.downloaded_bytes > self.total_bytes:
            raise ValueError("已下载字节数不能大于总字节数")
        return self

    @property
    def percentage(self) -> float | None:
        if self.total_bytes is None:
            return None
        return round(self.downloaded_bytes / self.total_bytes * 100, 2)

    @property
    def remaining_seconds(self) -> float | None:
        if (
            self.total_bytes is None
            or self.speed_bytes_per_second is None
            or self.speed_bytes_per_second <= 0
        ):
            return None
        remaining_bytes = max(self.total_bytes - self.downloaded_bytes, 0)
        return round(remaining_bytes / self.speed_bytes_per_second, 2)


class DownloadResult(DownloaderDataModel):
    target_path: Path
    file_size: int = Field(ge=0)
    mime_type: str | None = Field(default=None, min_length=1, max_length=128)
    checksum: str | None = Field(default=None, min_length=1, max_length=256)
    extra: dict[str, object] = Field(default_factory=dict)


ProgressCallback = Callable[[DownloadProgress], None]


class DownloadCancellationToken:
    def __init__(self) -> None:
        self._event = Event()
        self._resume_event = Event()
        self._resume_event.set()

    def cancel(self) -> None:
        self._event.set()
        self._resume_event.set()

    def pause(self) -> None:
        self._resume_event.clear()

    def resume(self) -> None:
        self._resume_event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    @property
    def is_paused(self) -> bool:
        return not self._resume_event.is_set()

    def wait_if_paused(self) -> None:
        while self.is_paused:
            self.raise_if_cancelled()
            self._resume_event.wait(timeout=0.1)
        self.raise_if_cancelled()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise DownloadCancelledError()


class DownloadError(Exception):
    """Base error raised by downloader implementations."""


class DownloadCancelledError(DownloadError):
    def __init__(self, message: str = "下载已取消") -> None:
        super().__init__(message)


class Downloader(ABC):
    """Contract implemented by all VideoCenter download providers."""

    name: str
    priority: int = 0
    supported_schemes: tuple[str, ...] = ("http", "https")

    def supports(self, request: DownloadRequest) -> bool:
        return request.scheme in self.supported_schemes

    @abstractmethod
    def download(
        self,
        request: DownloadRequest,
        *,
        progress_callback: ProgressCallback | None = None,
        cancellation_token: DownloadCancellationToken | None = None,
    ) -> DownloadResult:
        """Download one resource and return its standardized result."""
