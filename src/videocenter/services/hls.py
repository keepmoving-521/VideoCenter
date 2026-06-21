import logging
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from videocenter.core.config import get_settings
from videocenter.core.database import SessionLocal
from videocenter.core.exceptions import ConflictError, NotFoundError
from videocenter.models.hls import HlsTask, HlsTaskStatus
from videocenter.models.media import LocalResource
from videocenter.services.media_artwork import MEDIA_CACHE_DIRECTORY_NAME

logger = logging.getLogger(__name__)
HLS_SEGMENT_SECONDS = 6
HLS_TIMEOUT_SECONDS = 24 * 60 * 60
_hls_threads: dict[int, threading.Thread] = {}
_hls_lock = threading.Lock()


def create_or_reuse_hls_task(db: Session, resource: LocalResource) -> HlsTask:
    existing = db.scalar(
        select(HlsTask)
        .where(
            HlsTask.resource_id == resource.id,
            HlsTask.status.in_(
                [
                    HlsTaskStatus.WAITING,
                    HlsTaskStatus.RUNNING,
                    HlsTaskStatus.COMPLETED,
                ]
            ),
        )
        .order_by(HlsTask.id.desc())
    )
    if existing is not None:
        if existing.status != HlsTaskStatus.COMPLETED or _task_files_exist(existing):
            return existing

    task = HlsTask(resource_id=resource.id, status=HlsTaskStatus.WAITING)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def start_hls_task(task_id: int) -> None:
    with _hls_lock:
        if task_id in _hls_threads:
            return
        thread = threading.Thread(
            target=run_hls_task,
            args=(task_id,),
            name=f"videocenter-hls-{task_id}",
            daemon=True,
        )
        _hls_threads[task_id] = thread
    thread.start()


def run_hls_task(task_id: int) -> None:
    try:
        with SessionLocal() as db:
            task = db.get(HlsTask, task_id)
            if task is None:
                return
            resource = db.get(LocalResource, task.resource_id)
            if resource is None or not Path(resource.file_path).is_file():
                raise RuntimeError("本地视频文件不存在")
            executable = _ffmpeg_executable()
            if executable is None:
                raise RuntimeError("FFmpeg 不可用，无法执行 HLS 转码")

            output_directory = _output_directory(resource)
            if output_directory.exists():
                shutil.rmtree(output_directory)
            segments_directory = output_directory / "segments"
            segments_directory.mkdir(parents=True)
            playlist_path = output_directory / "index.m3u8"
            task.status = HlsTaskStatus.RUNNING
            task.started_at = datetime.now()
            task.progress = 5
            task.output_directory = str(output_directory)
            task.playlist_path = str(playlist_path)
            task.error_message = None
            db.commit()

            result = subprocess.run(
                [
                    executable,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    resource.file_path,
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a:0?",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-f",
                    "hls",
                    "-hls_time",
                    str(HLS_SEGMENT_SECONDS),
                    "-hls_playlist_type",
                    "vod",
                    "-hls_flags",
                    "independent_segments",
                    "-hls_segment_filename",
                    str(segments_directory / "segment%05d.ts"),
                    "-y",
                    str(playlist_path),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=HLS_TIMEOUT_SECONDS,
                check=False,
            )
            if result.returncode != 0 or not playlist_path.is_file():
                raise RuntimeError(result.stderr.strip() or "FFmpeg 未生成 HLS 播放列表")
            task.status = HlsTaskStatus.COMPLETED
            task.progress = 100
            task.completed_at = datetime.now()
            db.commit()
    except Exception as exc:
        with SessionLocal() as db:
            task = db.get(HlsTask, task_id)
            if task is not None:
                task.status = HlsTaskStatus.FAILED
                task.error_message = str(exc)
                task.completed_at = datetime.now()
                db.commit()
        logger.exception("HLS transcoding failed", extra={"hls_task_id": task_id})
    finally:
        with _hls_lock:
            _hls_threads.pop(task_id, None)


def restore_hls_tasks() -> int:
    with SessionLocal() as db:
        result = db.execute(
            update(HlsTask)
            .where(HlsTask.status.in_([HlsTaskStatus.WAITING, HlsTaskStatus.RUNNING]))
            .values(
                status=HlsTaskStatus.WAITING,
                progress=0,
                error_message=None,
                started_at=None,
                completed_at=None,
            )
        )
        task_ids = db.scalars(
            select(HlsTask.id).where(HlsTask.status == HlsTaskStatus.WAITING).order_by(HlsTask.id)
        ).all()
        db.commit()
    for task_id in task_ids:
        start_hls_task(task_id)
    return result.rowcount or 0


def hls_playlist_path(task: HlsTask) -> Path:
    if task.status != HlsTaskStatus.COMPLETED or not task.playlist_path:
        raise ConflictError("HLS 转码尚未完成", code="HLS_NOT_READY")
    path = Path(task.playlist_path).resolve()
    _ensure_hls_cache_path(path)
    if not path.is_file():
        raise NotFoundError("HLS 播放列表文件已丢失", code="HLS_PLAYLIST_MISSING")
    return path


def hls_segment_path(task: HlsTask, segment_name: str) -> Path:
    if not task.output_directory:
        raise ConflictError("HLS 转码尚未完成", code="HLS_NOT_READY")
    if Path(segment_name).name != segment_name or not segment_name.endswith(".ts"):
        raise ConflictError("HLS 分片名称无效", code="INVALID_HLS_SEGMENT")
    path = (Path(task.output_directory) / "segments" / segment_name).resolve()
    _ensure_hls_cache_path(path)
    if not path.is_file():
        raise NotFoundError("HLS 分片文件不存在", code="HLS_SEGMENT_MISSING")
    return path


def _output_directory(resource: LocalResource) -> Path:
    digest = (resource.checksum_sha256 or f"resource-{resource.id}")[:16]
    return (
        get_settings().media_root / MEDIA_CACHE_DIRECTORY_NAME / "hls" / f"{resource.id}-{digest}"
    ).resolve()


def _ffmpeg_executable() -> str | None:
    configured = get_settings().ffmpeg_path
    if configured is None:
        return shutil.which("ffmpeg")
    candidate = Path(configured).expanduser()
    return str(candidate.resolve()) if candidate.is_file() else None


def _ensure_hls_cache_path(path: Path) -> None:
    root = (get_settings().media_root / MEDIA_CACHE_DIRECTORY_NAME / "hls").resolve()
    if not path.is_relative_to(root):
        raise ConflictError("HLS 文件路径无效", code="INVALID_HLS_PATH")


def _task_files_exist(task: HlsTask) -> bool:
    return bool(task.playlist_path and Path(task.playlist_path).is_file())
