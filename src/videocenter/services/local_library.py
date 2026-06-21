import logging
import mimetypes
import threading
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from videocenter.core.config import get_settings
from videocenter.core.database import SessionLocal
from videocenter.models.media import LocalResource
from videocenter.models.scan import ScanTask, ScanTaskStatus

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".ts"}
logger = logging.getLogger(__name__)
_scan_threads: dict[int, threading.Thread] = {}
_scan_lock = threading.Lock()


def resolve_library_path(requested_path: str | None) -> Path:
    root = get_settings().media_root
    candidate = Path(requested_path).expanduser().resolve() if requested_path else root
    if not candidate.is_relative_to(root):
        raise ValueError("扫描目录必须位于媒体根目录内")
    if not candidate.is_dir():
        raise ValueError("扫描目录不存在")
    return candidate


def create_scan_task(
    db: Session,
    *,
    path: Path,
    media_id: int | None,
    incremental: bool,
) -> ScanTask:
    task = ScanTask(
        path=str(path),
        media_id=media_id,
        incremental=incremental,
        status=ScanTaskStatus.WAITING,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def start_scan_task(task_id: int) -> None:
    thread = threading.Thread(
        target=run_scan_task,
        args=(task_id,),
        name=f"videocenter-scan-{task_id}",
        daemon=True,
    )
    with _scan_lock:
        _scan_threads[task_id] = thread
    thread.start()


def run_scan_task(task_id: int) -> None:
    try:
        with SessionLocal() as db:
            task = db.get(ScanTask, task_id)
            if task is None:
                return
            task.status = ScanTaskStatus.RUNNING
            task.started_at = datetime.now()
            task.error_message = None
            db.commit()

            files = sorted(
                path
                for path in Path(task.path).rglob("*")
                if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
            )
            task.total_files = len(files)
            task.discovered_files = len(files)
            db.commit()

            for index, path in enumerate(files, start=1):
                _process_file(db, task, path)
                task.processed_files = index
                task.progress = round(index / len(files) * 100, 2) if files else 100
                db.commit()

            task.progress = 100
            task.status = ScanTaskStatus.COMPLETED
            task.completed_at = datetime.now()
            db.commit()
            logger.info(
                "Local media scan completed",
                extra={
                    "scan_task_id": task.id,
                    "scan_event": "completed",
                    "total_files": task.total_files,
                    "added_files": task.added_files,
                    "updated_files": task.updated_files,
                    "skipped_files": task.skipped_files,
                },
            )
    except Exception as exc:
        with SessionLocal() as db:
            task = db.get(ScanTask, task_id)
            if task is not None:
                task.status = ScanTaskStatus.FAILED
                task.error_message = str(exc)
                task.completed_at = datetime.now()
                db.commit()
        logger.exception(
            "Local media scan failed",
            extra={"scan_task_id": task_id, "scan_event": "failed"},
        )
    finally:
        with _scan_lock:
            _scan_threads.pop(task_id, None)


def _process_file(db: Session, task: ScanTask, path: Path) -> None:
    normalized = str(path.resolve())
    stat = path.stat()
    resource = db.scalar(select(LocalResource).where(LocalResource.file_path == normalized))
    if (
        resource is not None
        and task.incremental
        and resource.file_size == stat.st_size
        and resource.modified_at_ns == stat.st_mtime_ns
        and (task.media_id is None or resource.media_id == task.media_id)
    ):
        task.skipped_files += 1
        return

    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if resource is None:
        db.add(
            LocalResource(
                media_id=task.media_id,
                file_path=normalized,
                file_name=path.name,
                file_size=stat.st_size,
                mime_type=mime_type,
                modified_at_ns=stat.st_mtime_ns,
            )
        )
        task.added_files += 1
        return

    resource.file_name = path.name
    resource.file_size = stat.st_size
    resource.mime_type = mime_type
    resource.modified_at_ns = stat.st_mtime_ns
    if task.media_id is not None:
        resource.media_id = task.media_id
    task.updated_files += 1


def restore_scan_tasks() -> int:
    with SessionLocal() as db:
        result = db.execute(
            update(ScanTask)
            .where(ScanTask.status.in_([ScanTaskStatus.WAITING, ScanTaskStatus.RUNNING]))
            .values(
                status=ScanTaskStatus.WAITING,
                progress=0,
                processed_files=0,
                added_files=0,
                updated_files=0,
                skipped_files=0,
                error_message=None,
                started_at=None,
                completed_at=None,
            )
        )
        task_ids = db.scalars(
            select(ScanTask.id)
            .where(ScanTask.status == ScanTaskStatus.WAITING)
            .order_by(ScanTask.id)
        ).all()
        db.commit()
    for task_id in task_ids:
        start_scan_task(task_id)
    return result.rowcount or 0
