import hashlib
import logging
import re
import threading
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from videocenter.core.config import get_settings
from videocenter.core.database import SessionLocal
from videocenter.core.exceptions import ConflictError
from videocenter.models.download import DownloadStatus, DownloadTask
from videocenter.models.media import LocalResource, Media, MediaStatus
from videocenter.services.download_queue import DownloadTaskQueue
from videocenter.services.downloaders import (
    DownloadCancellationToken,
    DownloadCancelledError,
    Downloader,
    DownloadProgress,
    DownloadRequest,
    HttpDirectDownloader,
    YtDlpDownloader,
)
from videocenter.services.downloaders.base import normalize_download_url
from videocenter.services.local_file_hashes import calculate_sha256
from videocenter.services.local_resource_analysis import analyze_local_resource
from videocenter.services.notifications import create_download_completed_notification
from videocenter.services.video_filename import parse_video_filename

_default_downloader = HttpDirectDownloader()
_yt_dlp_downloader = YtDlpDownloader()
logger = logging.getLogger(__name__)
_queue_lock = threading.Lock()
_download_queue: DownloadTaskQueue | None = None
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
DIRECT_MEDIA_EXTENSIONS = {
    ".3gp",
    ".aac",
    ".avi",
    ".flac",
    ".m4a",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".ogg",
    ".opus",
    ".ts",
    ".wav",
    ".webm",
}


def safe_target_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", Path(name).name).strip(" .")
    if not cleaned:
        raise ValueError("无效的目标文件名")
    path = Path(cleaned)
    if path.stem.upper() in WINDOWS_RESERVED_NAMES:
        cleaned = f"{path.stem}_{path.suffix}"
    return cleaned


def start_download(task_id: int, *, priority: int = 0) -> None:
    if get_download_queue().enqueue(task_id, priority=priority):
        logger.info(
            "Download task queued",
            extra={
                "download_event": "queued",
                "download_task_id": task_id,
                "priority": priority,
            },
        )


def get_download_queue() -> DownloadTaskQueue:
    global _download_queue
    with _queue_lock:
        if _download_queue is None:
            _download_queue = DownloadTaskQueue(
                _run_download,
                worker_count=get_settings().download_worker_count,
            )
        return _download_queue


def restore_download_queue() -> int:
    with SessionLocal() as db:
        db.execute(
            update(DownloadTask)
            .where(DownloadTask.status == DownloadStatus.DOWNLOADING)
            .values(
                status=DownloadStatus.WAITING,
                progress=0,
                downloaded_bytes=0,
                total_bytes=None,
                speed_bytes_per_second=None,
                remaining_seconds=None,
                target_path=None,
                checksum_sha256=None,
            )
        )
        waiting_tasks = db.scalars(
            select(DownloadTask)
            .where(DownloadTask.status == DownloadStatus.WAITING)
            .order_by(DownloadTask.priority.desc(), DownloadTask.id)
        ).all()
        paused_tasks = db.scalars(
            select(DownloadTask)
            .where(DownloadTask.status == DownloadStatus.PAUSED)
            .order_by(DownloadTask.id)
        ).all()
        for task in [*waiting_tasks, *paused_tasks]:
            update_media_download_status(db, task.media_id)
            target_directory, _ = resolve_download_directory(task.target_directory)
            cleanup_download_temp_file(target_directory / safe_target_name(task.target_name))
        db.commit()
    queue_instance = get_download_queue()
    restored = 0
    for task in waiting_tasks:
        if queue_instance.enqueue(task.id, priority=task.priority):
            restored += 1
            logger.info(
                "Download task restored",
                extra={
                    "download_event": "restored",
                    "download_task_id": task.id,
                    "media_id": task.media_id,
                    "priority": task.priority,
                },
            )
    return restored


def cancel_download(db: Session, task: DownloadTask) -> DownloadTask:
    get_download_queue().cancel(task.id)
    if task.status in {
        DownloadStatus.WAITING,
        DownloadStatus.DOWNLOADING,
        DownloadStatus.PAUSED,
    }:
        task.status = DownloadStatus.CANCELLED
        task.speed_bytes_per_second = None
        task.remaining_seconds = None
        db.flush()
        update_media_download_status(db, task.media_id)
        db.commit()
        db.refresh(task)
        logger.info(
            "Download task cancelled",
            extra=download_log_context(task, event="cancelled"),
        )
    elif task.status != DownloadStatus.CANCELLED:
        raise ConflictError(
            "当前状态的下载任务不能取消",
            code="DOWNLOAD_NOT_CANCELLABLE",
            details={"status": task.status.value},
        )
    return task


def pause_download(db: Session, task: DownloadTask) -> DownloadTask:
    if task.status not in {DownloadStatus.WAITING, DownloadStatus.DOWNLOADING}:
        raise ConflictError(
            "当前状态的下载任务不能暂停",
            code="DOWNLOAD_NOT_PAUSABLE",
            details={"status": task.status.value},
        )
    get_download_queue().pause(task.id)
    task.status = DownloadStatus.PAUSED
    task.speed_bytes_per_second = None
    task.remaining_seconds = None
    update_media_download_status(db, task.media_id)
    db.commit()
    db.refresh(task)
    logger.info(
        "Download task paused",
        extra=download_log_context(task, event="paused"),
    )
    return task


def resume_download(db: Session, task: DownloadTask) -> DownloadTask:
    if task.status != DownloadStatus.PAUSED:
        raise ConflictError(
            "只有暂停状态的下载任务可以恢复",
            code="DOWNLOAD_NOT_RESUMABLE",
            details={"status": task.status.value},
        )
    queue_instance = get_download_queue()
    if queue_instance.resume(task.id):
        task.status = (
            DownloadStatus.DOWNLOADING
            if queue_instance.is_running(task.id)
            else DownloadStatus.WAITING
        )
    else:
        reset_download_metrics(task)
        task.status = DownloadStatus.WAITING
        queue_instance.enqueue(task.id, priority=task.priority)
    task.error_message = None
    update_media_download_status(db, task.media_id)
    db.commit()
    db.refresh(task)
    logger.info(
        "Download task resumed",
        extra=download_log_context(task, event="resumed"),
    )
    return task


def retry_download(db: Session, task: DownloadTask) -> DownloadTask:
    if task.status != DownloadStatus.FAILED:
        raise ConflictError(
            "只有失败的下载任务可以重试",
            code="DOWNLOAD_NOT_RETRYABLE",
            details={"status": task.status.value},
        )
    reset_download_metrics(task)
    task.status = DownloadStatus.WAITING
    task.error_message = None
    update_media_download_status(db, task.media_id)
    db.commit()
    get_download_queue().enqueue(task.id, priority=task.priority)
    db.refresh(task)
    logger.info(
        "Download task retry queued",
        extra=download_log_context(task, event="retry_queued"),
    )
    return task


def reset_download_metrics(task: DownloadTask) -> None:
    task.progress = 0
    task.downloaded_bytes = 0
    task.total_bytes = None
    task.speed_bytes_per_second = None
    task.remaining_seconds = None
    task.target_path = None


def normalized_download_source(source_url: str) -> str:
    return normalize_download_url(source_url)


def select_download_provider(
    source_url: str,
    requested_provider: str = "auto",
    *,
    requires_processing: bool = False,
) -> str:
    if requested_provider != "auto":
        return requested_provider
    if requires_processing:
        return "yt-dlp"
    suffix = Path(urlsplit(source_url).path).suffix.casefold()
    return "http-direct" if suffix in DIRECT_MEDIA_EXTENSIONS else "yt-dlp"


def get_downloader(name: str) -> Downloader:
    if name == "http-direct":
        return _default_downloader
    if name == "yt-dlp":
        return _yt_dlp_downloader
    raise ValueError(f"不支持的下载器：{name}")


def generate_target_name(
    source_url: str,
    *,
    media_title: str | None = None,
) -> str:
    parsed = urlsplit(source_url)
    url_name = unquote(Path(parsed.path).name)
    suffix = Path(url_name).suffix
    base_name = media_title or Path(url_name).stem or "download"
    safe_base = safe_target_name(base_name)
    safe_suffix = re.sub(r"[^A-Za-z0-9.]", "", suffix)[:16]
    digest = hashlib.sha256(source_url.encode()).hexdigest()[:10]
    max_base_length = 512 - len(digest) - len(safe_suffix) - 1
    trimmed_base = safe_base[:max_base_length].rstrip(" .-_") or "download"
    return f"{trimmed_base}-{digest}{safe_suffix}"


def resolve_download_directory(requested_directory: str | None) -> tuple[Path, str]:
    root = get_settings().media_root.resolve()
    if requested_directory is None:
        return root, ""
    requested_path = Path(requested_directory)
    candidate = (
        requested_path.expanduser().resolve()
        if requested_path.is_absolute()
        else (root / requested_path).resolve()
    )
    if not candidate.is_relative_to(root):
        raise ValueError("下载目标目录必须位于媒体根目录内")
    relative = candidate.relative_to(root)
    return candidate, "" if relative == Path(".") else relative.as_posix()


def cleanup_download_temp_file(target_path: Path) -> None:
    target_path.with_suffix(target_path.suffix + ".part").unlink(missing_ok=True)


def register_local_resource(
    db: Session,
    *,
    task: DownloadTask,
    result,
) -> LocalResource:
    normalized_path = str(result.target_path.resolve())
    resource = db.scalar(select(LocalResource).where(LocalResource.file_path == normalized_path))
    if resource is None:
        resource = LocalResource(file_path=normalized_path)
        db.add(resource)
    resource.media_id = task.media_id
    resource.file_name = result.target_path.name
    resource.file_size = result.file_size
    resource.mime_type = result.mime_type or "application/octet-stream"
    resource.checksum_sha256 = result.checksum
    if resource.checksum_sha256 is None and result.target_path.exists():
        resource.checksum_sha256 = calculate_sha256(result.target_path)
    resource.is_available = True
    resource.missing_at = None
    parsed = parse_video_filename(result.target_path.name)
    resource.detected_media_type = parsed.media_type.value
    resource.parsed_title = parsed.title
    resource.parsed_release_year = parsed.release_year
    resource.parsed_season_number = parsed.season_number
    resource.parsed_episode_number = parsed.episode_number
    if result.target_path.exists():
        resource.modified_at_ns = result.target_path.stat().st_mtime_ns
        analyze_local_resource(resource, force=True)
    return resource


def download_log_context(
    task: DownloadTask,
    *,
    event: str,
    **values,
) -> dict[str, object]:
    return {
        "download_event": event,
        "download_task_id": task.id,
        "media_id": task.media_id,
        "status": task.status.value,
        "priority": task.priority,
        **values,
    }


def update_media_download_status(db: Session, media_id: int | None) -> None:
    if media_id is None:
        return
    media = db.get(Media, media_id)
    if media is None:
        return
    local_resource_id = db.scalar(
        select(LocalResource.id)
        .where(
            LocalResource.media_id == media_id,
            LocalResource.is_available.is_(True),
        )
        .limit(1)
    )
    if local_resource_id is not None:
        media.status = MediaStatus.AVAILABLE
        return
    active_download_id = db.scalar(
        select(DownloadTask.id)
        .where(
            DownloadTask.media_id == media_id,
            DownloadTask.status.in_(
                [
                    DownloadStatus.WAITING,
                    DownloadStatus.DOWNLOADING,
                    DownloadStatus.PAUSED,
                ]
            ),
        )
        .limit(1)
    )
    if active_download_id is not None:
        media.status = MediaStatus.DOWNLOADING
        return
    has_missing_resource = db.scalar(
        select(LocalResource.id).where(LocalResource.media_id == media_id).limit(1)
    )
    media.status = MediaStatus.MISSING if has_missing_resource is not None else MediaStatus.PENDING


def _run_download(
    task_id: int,
    cancellation_token: DownloadCancellationToken,
    downloader: Downloader | None = None,
) -> None:
    started_at = time.perf_counter()
    try:
        with SessionLocal() as db:
            task = db.get(DownloadTask, task_id)
            if not task:
                return
            if (
                task.status
                in {
                    DownloadStatus.CANCELLED,
                    DownloadStatus.PAUSED,
                }
                or cancellation_token.is_cancelled
            ):
                return
            task.status = DownloadStatus.DOWNLOADING
            task.error_message = None
            selected_name = select_download_provider(
                task.source_url,
                task.downloader_name,
            )
            task.downloader_name = selected_name
            selected_downloader = downloader or get_downloader(selected_name)
            update_media_download_status(db, task.media_id)
            db.commit()
            logger.info(
                "Download task started",
                extra=download_log_context(
                    task,
                    event="started",
                    downloader=selected_downloader.name,
                ),
            )

            target_directory, _ = resolve_download_directory(task.target_directory)
            target = target_directory / safe_target_name(task.target_name)
            request = DownloadRequest(
                source_url=task.source_url,
                target_path=target,
                headers={"User-Agent": "VideoCenter/0.1"},
                timeout_seconds=30,
                overwrite=True,
                expected_sha256=task.expected_sha256,
                video_quality=task.video_quality,
                video_format=task.video_format,
                download_subtitles=task.download_subtitles,
                subtitle_languages=tuple(task.subtitle_languages),
                download_thumbnail=task.download_thumbnail,
            )

            last_logged_bucket = -1

            def update_progress(progress: DownloadProgress) -> None:
                nonlocal last_logged_bucket
                task.downloaded_bytes = progress.downloaded_bytes
                if progress.total_bytes is not None:
                    task.total_bytes = progress.total_bytes
                if progress.percentage is not None:
                    task.progress = progress.percentage
                if progress.speed_bytes_per_second is not None:
                    task.speed_bytes_per_second = round(
                        progress.speed_bytes_per_second,
                        2,
                    )
                task.remaining_seconds = progress.remaining_seconds
                db.commit()
                if progress.percentage is not None:
                    bucket = int(progress.percentage // 10)
                    if bucket > last_logged_bucket:
                        last_logged_bucket = bucket
                        logger.info(
                            "Download task progress updated",
                            extra=download_log_context(
                                task,
                                event="progress",
                                progress=task.progress,
                                downloaded_bytes=task.downloaded_bytes,
                                total_bytes=task.total_bytes,
                                speed_bytes_per_second=task.speed_bytes_per_second,
                                remaining_seconds=task.remaining_seconds,
                            ),
                        )

            result = selected_downloader.download(
                request,
                progress_callback=update_progress,
                cancellation_token=cancellation_token,
            )
            db.refresh(task)
            if task.status in {DownloadStatus.PAUSED, DownloadStatus.CANCELLED}:
                return
            task.target_path = str(result.target_path)
            task.progress = 100
            task.downloaded_bytes = result.file_size
            task.total_bytes = result.file_size
            task.remaining_seconds = 0
            task.checksum_sha256 = result.checksum
            task.status = DownloadStatus.COMPLETED
            register_local_resource(db, task=task, result=result)
            create_download_completed_notification(db, task=task)
            db.flush()
            update_media_download_status(db, task.media_id)
            db.commit()
            logger.info(
                "Download task completed",
                extra=download_log_context(
                    task,
                    event="completed",
                    file_size=result.file_size,
                    checksum_sha256=result.checksum,
                    duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
                ),
            )
    except DownloadCancelledError:
        with SessionLocal() as db:
            task = db.get(DownloadTask, task_id)
            if task:
                if task.status != DownloadStatus.PAUSED:
                    task.status = DownloadStatus.CANCELLED
                task.speed_bytes_per_second = None
                task.remaining_seconds = None
                db.flush()
                update_media_download_status(db, task.media_id)
                db.commit()
                logger.info(
                    "Download task cancelled during execution",
                    extra=download_log_context(task, event="cancelled"),
                )
    except Exception as exc:
        with SessionLocal() as db:
            task = db.get(DownloadTask, task_id)
            if task and task.status not in {
                DownloadStatus.CANCELLED,
                DownloadStatus.PAUSED,
            }:
                task.status = DownloadStatus.FAILED
                task.speed_bytes_per_second = None
                task.remaining_seconds = None
                task.error_message = str(exc)
                db.flush()
                update_media_download_status(db, task.media_id)
                db.commit()
                target_directory, _ = resolve_download_directory(task.target_directory)
                cleanup_download_temp_file(target_directory / safe_target_name(task.target_name))
                logger.exception(
                    "Download task failed",
                    extra=download_log_context(
                        task,
                        event="failed",
                        error_type=type(exc).__name__,
                        duration_ms=round(
                            (time.perf_counter() - started_at) * 1000,
                            2,
                        ),
                    ),
                )
