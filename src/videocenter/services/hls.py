import logging
import queue
import shutil
import subprocess
import threading
from collections.abc import Callable
from datetime import datetime, timedelta
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
_hls_lock = threading.Lock()
_hls_queue: "HlsTaskQueue | None" = None


class HlsTaskQueue:
    def __init__(self, runner: Callable[[int], None], *, worker_count: int) -> None:
        if worker_count < 1:
            raise ValueError("worker_count must be greater than zero")
        self._runner = runner
        self._queue: queue.Queue[int | None] = queue.Queue()
        self._queued_ids: set[int] = set()
        self._running_ids: set[int] = set()
        self._lock = threading.Lock()
        self._workers = [
            threading.Thread(
                target=self._worker,
                name=f"videocenter-hls-worker-{index + 1}",
                daemon=True,
            )
            for index in range(worker_count)
        ]
        for worker in self._workers:
            worker.start()

    def enqueue(self, task_id: int) -> bool:
        with self._lock:
            if task_id in self._queued_ids or task_id in self._running_ids:
                return False
            self._queued_ids.add(task_id)
        self._queue.put(task_id)
        return True

    @property
    def running_count(self) -> int:
        with self._lock:
            return len(self._running_ids)

    @property
    def waiting_count(self) -> int:
        with self._lock:
            return len(self._queued_ids)

    def join(self) -> None:
        self._queue.join()

    def shutdown(self) -> None:
        for _ in self._workers:
            self._queue.put(None)
        for worker in self._workers:
            worker.join(timeout=5)

    def _worker(self) -> None:
        while True:
            task_id = self._queue.get()
            try:
                if task_id is None:
                    return
                with self._lock:
                    self._queued_ids.discard(task_id)
                    self._running_ids.add(task_id)
                self._runner(task_id)
            finally:
                if task_id is not None:
                    with self._lock:
                        self._running_ids.discard(task_id)
                self._queue.task_done()


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
    get_hls_queue().enqueue(task_id)


def get_hls_queue() -> HlsTaskQueue:
    global _hls_queue
    with _hls_lock:
        if _hls_queue is None:
            _hls_queue = HlsTaskQueue(
                run_hls_task,
                worker_count=get_settings().hls_worker_count,
            )
        return _hls_queue


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

            command = [
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
                "-progress",
                "pipe:1",
                "-nostats",
                "-y",
                str(playlist_path),
            ]
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            _consume_ffmpeg_progress(db, task, process, resource.duration_seconds)
            stderr = process.stderr.read() if process.stderr else ""
            return_code = process.wait(timeout=HLS_TIMEOUT_SECONDS)
            if return_code != 0 or not playlist_path.is_file():
                raise RuntimeError(stderr.strip() or "FFmpeg 未生成 HLS 播放列表")
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


def cleanup_hls_cache(
    db: Session,
    *,
    max_age_hours: int | None = None,
) -> tuple[list[int], int, int]:
    retention = get_settings().hls_cache_retention_hours if max_age_hours is None else max_age_hours
    cutoff = datetime.now() - timedelta(hours=retention)
    tasks = db.scalars(
        select(HlsTask).where(
            HlsTask.status.in_([HlsTaskStatus.COMPLETED, HlsTaskStatus.FAILED]),
            HlsTask.completed_at.is_not(None),
            HlsTask.completed_at <= cutoff,
        )
    ).all()
    cleaned_ids: list[int] = []
    removed_directories = 0
    reclaimed_bytes = 0
    for task in tasks:
        if task.output_directory:
            directory = Path(task.output_directory).resolve()
            _ensure_hls_cache_path(directory)
            if directory.is_dir():
                reclaimed_bytes += _directory_size(directory)
                shutil.rmtree(directory)
                removed_directories += 1
        task.output_directory = None
        task.playlist_path = None
        cleaned_ids.append(task.id)
    db.commit()
    return cleaned_ids, removed_directories, reclaimed_bytes


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


def _consume_ffmpeg_progress(
    db: Session,
    task: HlsTask,
    process: subprocess.Popen,
    duration_seconds: float | None,
) -> None:
    if process.stdout is None:
        return
    last_progress = task.progress
    for raw_line in process.stdout:
        key, separator, value = raw_line.strip().partition("=")
        if not separator or key not in {"out_time_us", "out_time_ms"}:
            continue
        try:
            elapsed_seconds = int(value) / 1_000_000
        except ValueError:
            continue
        if duration_seconds and duration_seconds > 0:
            progress = min(round(elapsed_seconds / duration_seconds * 100, 2), 99)
        else:
            progress = min(last_progress + 1, 99)
        if progress <= last_progress:
            continue
        task.progress = progress
        last_progress = progress
        db.commit()


def _directory_size(directory: Path) -> int:
    total = 0
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        try:
            total += path.stat().st_size
        except OSError:
            continue
    return total
