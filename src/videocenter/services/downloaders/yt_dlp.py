import hashlib
import importlib
import mimetypes
from pathlib import Path
from typing import Any

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


class YtDlpDownloader(Downloader):
    """Download site pages and streaming media through yt-dlp."""

    name = "yt-dlp"
    priority = 100

    def __init__(self, youtube_dl_class=None) -> None:
        self._youtube_dl_class = youtube_dl_class

    def download(
        self,
        request: DownloadRequest,
        *,
        progress_callback: ProgressCallback | None = None,
        cancellation_token: DownloadCancellationToken | None = None,
    ) -> DownloadResult:
        token = cancellation_token or DownloadCancellationToken()
        target_path = request.target_path.expanduser().resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        output_template = str(target_path.with_suffix("")) + ".%(ext)s"
        youtube_dl_class = self._youtube_dl_class or self._load_youtube_dl()
        final_path: Path | None = None

        def progress_hook(data: dict[str, Any]) -> None:
            nonlocal final_path
            token.wait_if_paused()
            status = data.get("status")
            filename = data.get("filename")
            if filename:
                final_path = Path(filename).expanduser().resolve()
            if status == "downloading":
                downloaded = max(int(data.get("downloaded_bytes") or 0), 0)
                total = data.get("total_bytes") or data.get("total_bytes_estimate")
                total_bytes = int(total) if total and int(total) > 0 else None
                if total_bytes is not None and downloaded > total_bytes:
                    total_bytes = None
                speed = data.get("speed")
                self._report(
                    progress_callback,
                    DownloadProgress(
                        state=DownloadProgressState.DOWNLOADING,
                        downloaded_bytes=downloaded,
                        total_bytes=total_bytes,
                        speed_bytes_per_second=(
                            float(speed) if speed is not None and float(speed) >= 0 else None
                        ),
                    ),
                )
            elif status == "finished":
                self._report(
                    progress_callback,
                    DownloadProgress(
                        state=DownloadProgressState.FINALIZING,
                        downloaded_bytes=max(int(data.get("downloaded_bytes") or 0), 0),
                    ),
                )

        options = {
            "format": self._format_selector(
                request.video_quality,
                request.video_format,
            ),
            "outtmpl": output_template,
            "noplaylist": True,
            "overwrites": request.overwrite,
            "continuedl": True,
            "quiet": True,
            "no_warnings": True,
            "http_headers": request.headers,
            "socket_timeout": request.timeout_seconds,
            "progress_hooks": [progress_hook],
            "writesubtitles": request.download_subtitles,
            "writeautomaticsub": False,
            "subtitleslangs": list(request.subtitle_languages) or ["all"],
            "subtitlesformat": "best",
            "writethumbnail": request.download_thumbnail,
        }
        if request.video_format != "best":
            options["merge_output_format"] = request.video_format

        try:
            token.raise_if_cancelled()
            self._report(
                progress_callback,
                DownloadProgress(state=DownloadProgressState.STARTING),
            )
            with youtube_dl_class(options) as ydl:
                info = ydl.extract_info(request.source_url, download=True)
                prepared_path = Path(ydl.prepare_filename(info)).expanduser().resolve()
            token.raise_if_cancelled()
            final_path = self._find_output_path(target_path, final_path, prepared_path)
            file_size = final_path.stat().st_size
            checksum = self._sha256(final_path)
            if request.expected_sha256 is not None and checksum != request.expected_sha256:
                final_path.unlink(missing_ok=True)
                raise DownloadError(
                    f"下载文件 SHA-256 校验失败：预期 {request.expected_sha256}，实际 {checksum}"
                )
            return DownloadResult(
                target_path=final_path,
                file_size=file_size,
                mime_type=mimetypes.guess_type(final_path.name)[0] or "application/octet-stream",
                checksum=checksum,
                extra={
                    "extractor": info.get("extractor_key") or info.get("extractor"),
                    "format_id": info.get("format_id"),
                    "subtitle_paths": self._sidecar_paths(
                        final_path,
                        {".srt", ".vtt", ".ass", ".lrc"},
                    ),
                    "thumbnail_paths": self._sidecar_paths(
                        final_path,
                        {".jpg", ".jpeg", ".png", ".webp"},
                    ),
                },
            )
        except DownloadCancelledError:
            self._cleanup_output_files(target_path)
            raise
        except DownloadError:
            self._cleanup_output_files(target_path)
            raise
        except Exception as exc:
            self._cleanup_output_files(target_path)
            if token.is_cancelled:
                raise DownloadCancelledError() from exc
            raise DownloadError(f"yt-dlp 下载失败：{exc}") from exc

    @staticmethod
    def _load_youtube_dl():
        try:
            return importlib.import_module("yt_dlp").YoutubeDL
        except (ImportError, AttributeError) as exc:
            raise DownloadError("yt-dlp 未安装，请先同步项目运行依赖") from exc

    @staticmethod
    def _find_output_path(
        target_path: Path,
        hook_path: Path | None,
        prepared_path: Path,
    ) -> Path:
        for candidate in (hook_path, prepared_path, target_path):
            if candidate is not None and candidate.is_file():
                return candidate
        matches = sorted(
            (
                path
                for path in target_path.parent.glob(f"{target_path.stem}.*")
                if path.is_file() and path.suffix not in {".part", ".ytdl"}
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if matches:
            return matches[0].resolve()
        raise DownloadError("yt-dlp 未生成可用的下载文件")

    @staticmethod
    def _format_selector(video_quality: str, video_format: str) -> str:
        height = None if video_quality == "best" else int(video_quality.removesuffix("p"))
        height_filter = "" if height is None else f"[height<={height}]"
        if video_format == "best":
            return f"bestvideo*{height_filter}+bestaudio/best{height_filter}"
        return (
            f"bestvideo*{height_filter}[ext={video_format}]+bestaudio/"
            f"best{height_filter}[ext={video_format}]/"
            f"bestvideo*{height_filter}+bestaudio/best{height_filter}"
        )

    @staticmethod
    def _sidecar_paths(final_path: Path, extensions: set[str]) -> list[str]:
        return sorted(
            str(path.resolve())
            for path in final_path.parent.glob(f"{final_path.stem}.*")
            if path.is_file() and path.suffix.casefold() in extensions
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        checksum = hashlib.sha256()
        with path.open("rb") as file:
            while chunk := file.read(1024 * 1024):
                checksum.update(chunk)
        return checksum.hexdigest()

    @staticmethod
    def _cleanup_output_files(target_path: Path) -> None:
        for path in target_path.parent.glob(f"{target_path.stem}.*"):
            if path.is_file():
                path.unlink(missing_ok=True)

    @staticmethod
    def _report(
        callback: ProgressCallback | None,
        progress: DownloadProgress,
    ) -> None:
        if callback is not None:
            callback(progress)
