import mimetypes
import re
import threading
import urllib.request
from pathlib import Path

from sqlalchemy.orm import Session

from videocenter.core.config import get_settings
from videocenter.core.database import SessionLocal
from videocenter.models.download import DownloadStatus, DownloadTask
from videocenter.models.media import LocalResource

_cancel_events: dict[int, threading.Event] = {}
_events_lock = threading.Lock()


def safe_target_name(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", Path(name).name).strip(" .")
    if not cleaned:
        raise ValueError("无效的目标文件名")
    return cleaned


def start_download(task_id: int) -> None:
    event = threading.Event()
    with _events_lock:
        _cancel_events[task_id] = event
    threading.Thread(target=_run_download, args=(task_id, event), daemon=True).start()


def cancel_download(db: Session, task: DownloadTask) -> DownloadTask:
    with _events_lock:
        event = _cancel_events.get(task.id)
    if event:
        event.set()
    if task.status in {DownloadStatus.PENDING, DownloadStatus.RUNNING}:
        task.status = DownloadStatus.CANCELLED
        db.commit()
        db.refresh(task)
    return task


def _run_download(task_id: int, cancel_event: threading.Event) -> None:
    temp_path: Path | None = None
    try:
        with SessionLocal() as db:
            task = db.get(DownloadTask, task_id)
            if not task:
                return
            if task.status == DownloadStatus.CANCELLED or cancel_event.is_set():
                return
            task.status = DownloadStatus.RUNNING
            db.commit()

            target = get_settings().media_root / safe_target_name(task.target_name)
            target.parent.mkdir(parents=True, exist_ok=True)
            temp_path = target.with_suffix(target.suffix + ".part")
            request = urllib.request.Request(
                task.source_url, headers={"User-Agent": "VideoCenter/0.1"}
            )
            with urllib.request.urlopen(request, timeout=30) as response, temp_path.open("wb") as output:
                total = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                while chunk := response.read(1024 * 1024):
                    if cancel_event.is_set():
                        task.status = DownloadStatus.CANCELLED
                        db.commit()
                        return
                    output.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        task.progress = round(downloaded / total * 100, 2)
                        db.commit()

            temp_path.replace(target)
            task.target_path = str(target.resolve())
            task.progress = 100
            task.status = DownloadStatus.COMPLETED
            db.add(
                LocalResource(
                    media_id=task.media_id,
                    file_path=str(target.resolve()),
                    file_name=target.name,
                    file_size=target.stat().st_size,
                    mime_type=mimetypes.guess_type(target.name)[0]
                    or "application/octet-stream",
                )
            )
            db.commit()
    except Exception as exc:
        with SessionLocal() as db:
            task = db.get(DownloadTask, task_id)
            if task and task.status != DownloadStatus.CANCELLED:
                task.status = DownloadStatus.FAILED
                task.error_message = str(exc)
                db.commit()
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        with _events_lock:
            _cancel_events.pop(task_id, None)
