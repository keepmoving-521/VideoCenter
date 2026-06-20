import re
import threading
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from videocenter.core.config import get_settings
from videocenter.core.database import SessionLocal
from videocenter.core.exceptions import ConflictError
from videocenter.models.download import DownloadStatus, DownloadTask
from videocenter.models.media import LocalResource
from videocenter.services.download_queue import DownloadTaskQueue
from videocenter.services.downloaders import (
    DownloadCancellationToken,
    DownloadCancelledError,
    Downloader,
    DownloadProgress,
    DownloadRequest,
    HttpDirectDownloader,
)

_default_downloader = HttpDirectDownloader()
_queue_lock = threading.Lock()
_download_queue: DownloadTaskQueue | None = None


def safe_target_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", Path(name).name).strip(" .")
    if not cleaned:
        raise ValueError("无效的目标文件名")
    return cleaned


def start_download(task_id: int) -> None:
    get_download_queue().enqueue(task_id)


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
            )
        )
        waiting_ids = db.scalars(
            select(DownloadTask.id)
            .where(DownloadTask.status == DownloadStatus.WAITING)
            .order_by(DownloadTask.id)
        ).all()
        db.commit()
    queue_instance = get_download_queue()
    return sum(queue_instance.enqueue(task_id) for task_id in waiting_ids)


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
        db.commit()
        db.refresh(task)
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
    db.commit()
    db.refresh(task)
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
        queue_instance.enqueue(task.id)
    task.error_message = None
    db.commit()
    db.refresh(task)
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
    db.commit()
    get_download_queue().enqueue(task.id)
    db.refresh(task)
    return task


def reset_download_metrics(task: DownloadTask) -> None:
    task.progress = 0
    task.downloaded_bytes = 0
    task.total_bytes = None
    task.speed_bytes_per_second = None
    task.remaining_seconds = None
    task.target_path = None


def _run_download(
    task_id: int,
    cancellation_token: DownloadCancellationToken,
    downloader: Downloader = _default_downloader,
) -> None:
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
            db.commit()

            target = get_settings().media_root / safe_target_name(task.target_name)
            request = DownloadRequest(
                source_url=task.source_url,
                target_path=target,
                headers={"User-Agent": "VideoCenter/0.1"},
                timeout_seconds=30,
                overwrite=True,
            )

            def update_progress(progress: DownloadProgress) -> None:
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

            result = downloader.download(
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
            task.status = DownloadStatus.COMPLETED
            db.add(
                LocalResource(
                    media_id=task.media_id,
                    file_path=str(result.target_path),
                    file_name=result.target_path.name,
                    file_size=result.file_size,
                    mime_type=result.mime_type or "application/octet-stream",
                )
            )
            db.commit()
    except DownloadCancelledError:
        with SessionLocal() as db:
            task = db.get(DownloadTask, task_id)
            if task:
                if task.status != DownloadStatus.PAUSED:
                    task.status = DownloadStatus.CANCELLED
                task.speed_bytes_per_second = None
                task.remaining_seconds = None
                db.commit()
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
                db.commit()
