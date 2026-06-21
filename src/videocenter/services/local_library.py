import logging
import mimetypes
import threading
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from videocenter.core.config import get_settings
from videocenter.core.database import SessionLocal
from videocenter.models.media import LocalResource
from videocenter.models.scan import ScanTask, ScanTaskStatus
from videocenter.services.downloads import update_media_download_status
from videocenter.services.local_file_hashes import calculate_sha256
from videocenter.services.media_artwork import (
    MEDIA_CACHE_DIRECTORY_NAME,
    GeneratedVideoArtwork,
    generate_video_artwork,
)
from videocenter.services.media_probe import VideoMediaInfo, probe_video_file
from videocenter.services.video_filename import ParsedVideoFilename, parse_video_filename

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".ts"}
TRASH_DIRECTORY_NAME = ".videocenter-trash"
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
                if path.is_file()
                and path.suffix.lower() in VIDEO_EXTENSIONS
                and TRASH_DIRECTORY_NAME not in path.parts
                and MEDIA_CACHE_DIRECTORY_NAME not in path.parts
            )
            task.total_files = len(files)
            task.discovered_files = len(files)
            db.commit()

            discovered_paths = {str(path.resolve()) for path in files}
            affected_media_ids: set[int] = set()
            for index, path in enumerate(files, start=1):
                media_id = _process_file(db, task, path)
                if media_id is not None:
                    affected_media_ids.add(media_id)
                task.processed_files = index
                task.progress = round(index / len(files) * 100, 2) if files else 100
                db.commit()

            affected_media_ids.update(
                _mark_missing_resources(
                    db,
                    task=task,
                    discovered_paths=discovered_paths,
                )
            )
            db.flush()
            for media_id in affected_media_ids:
                update_media_download_status(db, media_id)
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
                    "missing_files": task.missing_files,
                    "restored_files": task.restored_files,
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


def _process_file(db: Session, task: ScanTask, path: Path) -> int | None:
    normalized = str(path.resolve())
    stat = path.stat()
    resource = db.scalar(select(LocalResource).where(LocalResource.file_path == normalized))
    if (
        resource is not None
        and task.incremental
        and resource.file_size == stat.st_size
        and resource.modified_at_ns == stat.st_mtime_ns
        and (task.media_id is None or resource.media_id == task.media_id)
        and resource.is_available
        and resource.parsed_title is not None
        and resource.checksum_sha256 is not None
        and resource.media_info_probed
        and resource.visual_assets_generated is not None
    ):
        task.skipped_files += 1
        return resource.media_id

    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    parsed = parse_video_filename(path.name)
    checksum_sha256 = calculate_sha256(path)
    media_info = probe_video_file(path)
    artwork = generate_video_artwork(
        path,
        checksum_sha256=checksum_sha256,
        duration_seconds=media_info.duration_seconds if media_info else None,
    )
    if resource is None:
        resource = LocalResource(
            media_id=task.media_id,
            file_path=normalized,
            file_name=path.name,
            file_size=stat.st_size,
            mime_type=mime_type,
            modified_at_ns=stat.st_mtime_ns,
            checksum_sha256=checksum_sha256,
        )
        _apply_parsed_filename(resource, parsed)
        _apply_media_info(resource, media_info)
        _apply_artwork(resource, artwork)
        db.add(resource)
        task.added_files += 1
        return task.media_id

    was_missing = not resource.is_available
    resource.file_name = path.name
    resource.file_size = stat.st_size
    resource.mime_type = mime_type
    resource.modified_at_ns = stat.st_mtime_ns
    resource.checksum_sha256 = checksum_sha256
    resource.is_available = True
    resource.missing_at = None
    _apply_parsed_filename(resource, parsed)
    _apply_media_info(resource, media_info)
    _apply_artwork(resource, artwork)
    if task.media_id is not None:
        resource.media_id = task.media_id
    if was_missing:
        task.restored_files += 1
    else:
        task.updated_files += 1
    return resource.media_id


def _apply_parsed_filename(
    resource: LocalResource,
    parsed: ParsedVideoFilename,
) -> None:
    resource.detected_media_type = parsed.media_type.value
    resource.parsed_title = parsed.title
    resource.parsed_release_year = parsed.release_year
    resource.parsed_season_number = parsed.season_number
    resource.parsed_episode_number = parsed.episode_number


def _apply_media_info(
    resource: LocalResource,
    media_info: VideoMediaInfo | None,
) -> None:
    resource.media_info_probed = True
    resource.duration_seconds = media_info.duration_seconds if media_info else None
    resource.video_width = media_info.width if media_info else None
    resource.video_height = media_info.height if media_info else None
    resource.video_codec = media_info.video_codec if media_info else None
    resource.bitrate = media_info.bitrate if media_info else None
    resource.audio_codec = media_info.audio_codec if media_info else None
    resource.audio_tracks = (
        [asdict(track) for track in media_info.audio_tracks] if media_info else []
    )
    resource.embedded_subtitles = (
        [asdict(track) for track in media_info.subtitle_tracks] if media_info else []
    )


def _apply_artwork(
    resource: LocalResource,
    artwork: GeneratedVideoArtwork | None,
) -> None:
    resource.visual_assets_generated = artwork is not None
    resource.cover_image_path = artwork.cover_image_path if artwork else None
    resource.preview_thumbnail_paths = list(artwork.preview_thumbnail_paths) if artwork else []


def _mark_missing_resources(
    db: Session,
    *,
    task: ScanTask,
    discovered_paths: set[str],
) -> set[int]:
    directory = Path(task.path).resolve()
    affected_media_ids: set[int] = set()
    resources = db.scalars(select(LocalResource)).all()
    for resource in resources:
        resource_path = Path(resource.file_path)
        try:
            is_in_directory = resource_path.is_relative_to(directory)
        except ValueError:
            is_in_directory = False
        if (
            not is_in_directory
            or resource.file_path in discovered_paths
            or not resource.is_available
        ):
            continue
        resource.is_available = False
        resource.missing_at = datetime.now()
        task.missing_files += 1
        if resource.media_id is not None:
            affected_media_ids.add(resource.media_id)
    return affected_media_ids


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
                missing_files=0,
                restored_files=0,
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
