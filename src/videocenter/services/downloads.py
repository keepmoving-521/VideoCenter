import re
import threading
from pathlib import Path

from sqlalchemy.orm import Session

from videocenter.core.config import get_settings
from videocenter.core.database import SessionLocal
from videocenter.models.download import DownloadStatus, DownloadTask
from videocenter.models.media import LocalResource
from videocenter.services.downloaders import (
    DownloadCancellationToken,
    DownloadCancelledError,
    Downloader,
    DownloadProgress,
    DownloadRequest,
    HttpDirectDownloader,
)

_cancel_tokens: dict[int, DownloadCancellationToken] = {}
_events_lock = threading.Lock()
_default_downloader = HttpDirectDownloader()


def safe_target_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", Path(name).name).strip(" .")
    if not cleaned:
        raise ValueError("无效的目标文件名")
    return cleaned


def start_download(task_id: int) -> None:
    token = DownloadCancellationToken()
    with _events_lock:
        _cancel_tokens[task_id] = token
    threading.Thread(target=_run_download, args=(task_id, token), daemon=True).start()


def cancel_download(db: Session, task: DownloadTask) -> DownloadTask:
    with _events_lock:
        token = _cancel_tokens.get(task.id)
    if token:
        token.cancel()
    if task.status in {DownloadStatus.PENDING, DownloadStatus.RUNNING}:
        task.status = DownloadStatus.CANCELLED
        db.commit()
        db.refresh(task)
    return task


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
            if task.status == DownloadStatus.CANCELLED or cancellation_token.is_cancelled:
                return
            task.status = DownloadStatus.RUNNING
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
                if progress.percentage is not None:
                    task.progress = progress.percentage
                    db.commit()

            result = downloader.download(
                request,
                progress_callback=update_progress,
                cancellation_token=cancellation_token,
            )
            task.target_path = str(result.target_path)
            task.progress = 100
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
                task.status = DownloadStatus.CANCELLED
                db.commit()
    except Exception as exc:
        with SessionLocal() as db:
            task = db.get(DownloadTask, task_id)
            if task and task.status != DownloadStatus.CANCELLED:
                task.status = DownloadStatus.FAILED
                task.error_message = str(exc)
                db.commit()
    finally:
        with _events_lock:
            _cancel_tokens.pop(task_id, None)
