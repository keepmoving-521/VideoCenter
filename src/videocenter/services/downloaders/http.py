import mimetypes
import time
import urllib.request

from videocenter.services.downloaders.base import (
    DownloadCancellationToken,
    DownloadCancelledError,
    Downloader,
    DownloadError,
    DownloadProgress,
    DownloadProgressState,
    DownloadRequest,
    DownloadResult,
    ProgressCallback,
)


class HttpDirectDownloader(Downloader):
    """Download direct HTTP/HTTPS resources into a local file."""

    name = "http-direct"
    priority = 0
    supported_schemes = ("http", "https")

    def download(
        self,
        request: DownloadRequest,
        *,
        progress_callback: ProgressCallback | None = None,
        cancellation_token: DownloadCancellationToken | None = None,
    ) -> DownloadResult:
        token = cancellation_token or DownloadCancellationToken()
        target_path = request.target_path.expanduser().resolve()
        temp_path = target_path.with_suffix(target_path.suffix + ".part")
        downloaded_bytes = 0
        total_bytes: int | None = None
        started_at = time.monotonic()

        try:
            token.raise_if_cancelled()
            if target_path.exists() and not request.overwrite:
                raise DownloadError(f"目标文件已存在：{target_path}")

            target_path.parent.mkdir(parents=True, exist_ok=True)
            self._report(
                progress_callback,
                DownloadProgress(state=DownloadProgressState.STARTING),
            )
            http_request = urllib.request.Request(
                request.source_url,
                headers=request.headers,
            )
            with (
                urllib.request.urlopen(
                    http_request,
                    timeout=request.timeout_seconds,
                ) as response,
                temp_path.open("wb") as output,
            ):
                total_bytes = self._content_length(response.headers.get("Content-Length"))
                while True:
                    token.wait_if_paused()
                    chunk = response.read(request.chunk_size)
                    if not chunk:
                        break
                    token.raise_if_cancelled()
                    output.write(chunk)
                    downloaded_bytes += len(chunk)
                    elapsed = max(time.monotonic() - started_at, 0.000001)
                    reported_total = (
                        total_bytes
                        if total_bytes is None or downloaded_bytes <= total_bytes
                        else None
                    )
                    self._report(
                        progress_callback,
                        DownloadProgress(
                            state=DownloadProgressState.DOWNLOADING,
                            downloaded_bytes=downloaded_bytes,
                            total_bytes=reported_total,
                            speed_bytes_per_second=downloaded_bytes / elapsed,
                        ),
                    )

            token.raise_if_cancelled()
            self._report(
                progress_callback,
                DownloadProgress(
                    state=DownloadProgressState.FINALIZING,
                    downloaded_bytes=downloaded_bytes,
                    total_bytes=total_bytes if total_bytes == downloaded_bytes else None,
                ),
            )
            if request.overwrite:
                temp_path.replace(target_path)
            else:
                temp_path.rename(target_path)
            return DownloadResult(
                target_path=target_path,
                file_size=downloaded_bytes,
                mime_type=(
                    response.headers.get_content_type()
                    if hasattr(response.headers, "get_content_type")
                    else mimetypes.guess_type(target_path.name)[0]
                )
                or "application/octet-stream",
            )
        except DownloadCancelledError:
            raise
        except DownloadError:
            raise
        except Exception as exc:
            raise DownloadError(f"HTTP 直链下载失败：{exc}") from exc
        finally:
            temp_path.unlink(missing_ok=True)

    @staticmethod
    def _content_length(value: str | None) -> int | None:
        if value is None:
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    @staticmethod
    def _report(
        callback: ProgressCallback | None,
        progress: DownloadProgress,
    ) -> None:
        if callback is not None:
            callback(progress)
