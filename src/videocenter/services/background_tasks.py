from datetime import datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.models.analysis import AnalysisTask
from videocenter.models.background_task import (
    BackgroundTask,
    BackgroundTaskLog,
    BackgroundTaskStatus,
    BackgroundTaskType,
)
from videocenter.models.download import DownloadTask
from videocenter.models.hls import HlsTask
from videocenter.models.scan import ScanTask

ALLOWED_STATUS_TRANSITIONS: dict[
    BackgroundTaskStatus,
    frozenset[BackgroundTaskStatus],
] = {
    BackgroundTaskStatus.WAITING: frozenset(
        {
            BackgroundTaskStatus.RUNNING,
            BackgroundTaskStatus.CANCELLED,
        }
    ),
    BackgroundTaskStatus.RUNNING: frozenset(
        {
            BackgroundTaskStatus.PAUSED,
            BackgroundTaskStatus.COMPLETED,
            BackgroundTaskStatus.FAILED,
            BackgroundTaskStatus.CANCELLED,
        }
    ),
    BackgroundTaskStatus.PAUSED: frozenset(
        {
            BackgroundTaskStatus.WAITING,
            BackgroundTaskStatus.RUNNING,
            BackgroundTaskStatus.CANCELLED,
        }
    ),
    BackgroundTaskStatus.COMPLETED: frozenset(),
    BackgroundTaskStatus.FAILED: frozenset({BackgroundTaskStatus.WAITING}),
    BackgroundTaskStatus.CANCELLED: frozenset(),
}


class InvalidTaskStatusTransition(ValueError):
    def __init__(
        self,
        current_status: BackgroundTaskStatus,
        target_status: BackgroundTaskStatus,
    ) -> None:
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(f"不允许后台任务从 {current_status.value} 转换为 {target_status.value}")


def normalize_task_status(status: StrEnum | str) -> BackgroundTaskStatus:
    value = status.value if isinstance(status, StrEnum) else status
    normalized = value.strip().lower()
    if normalized == "downloading":
        normalized = BackgroundTaskStatus.RUNNING.value
    return BackgroundTaskStatus(normalized)


def allowed_target_statuses(
    status: BackgroundTaskStatus,
) -> frozenset[BackgroundTaskStatus]:
    return ALLOWED_STATUS_TRANSITIONS[status]


def can_transition_task_status(
    current_status: BackgroundTaskStatus,
    target_status: BackgroundTaskStatus,
) -> bool:
    return current_status == target_status or target_status in allowed_target_statuses(
        current_status
    )


def transition_background_task(
    task: BackgroundTask,
    target_status: BackgroundTaskStatus,
    *,
    worker_id: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    now: datetime | None = None,
) -> BackgroundTask:
    current_status = task.status
    if current_status == target_status:
        return task
    if not can_transition_task_status(current_status, target_status):
        raise InvalidTaskStatusTransition(current_status, target_status)
    if target_status == BackgroundTaskStatus.PAUSED and not task.pause_supported:
        raise InvalidTaskStatusTransition(current_status, target_status)
    if target_status == BackgroundTaskStatus.CANCELLED and not task.cancellable:
        raise InvalidTaskStatusTransition(current_status, target_status)
    if (
        current_status == BackgroundTaskStatus.FAILED
        and target_status == BackgroundTaskStatus.WAITING
    ):
        if task.attempt >= task.max_attempts:
            raise InvalidTaskStatusTransition(current_status, target_status)
        task.attempt += 1

    changed_at = now or datetime.now()
    task.status = target_status
    if target_status == BackgroundTaskStatus.WAITING:
        task.worker_id = None
        task.heartbeat_at = None
        task.completed_at = None
        task.error_code = None
        task.error_message = None
        task.cancel_requested = False
    elif target_status == BackgroundTaskStatus.RUNNING:
        task.started_at = task.started_at or changed_at
        task.completed_at = None
        task.worker_id = worker_id
        task.heartbeat_at = changed_at
        task.error_code = None
        task.error_message = None
    elif target_status == BackgroundTaskStatus.PAUSED:
        task.worker_id = None
        task.heartbeat_at = changed_at
    elif target_status == BackgroundTaskStatus.COMPLETED:
        task.progress = 100
        if task.total_items is not None:
            task.processed_items = task.total_items
        task.completed_at = changed_at
        task.heartbeat_at = changed_at
        task.error_code = None
        task.error_message = None
        task.cancel_requested = False
    elif target_status == BackgroundTaskStatus.FAILED:
        task.completed_at = changed_at
        task.heartbeat_at = changed_at
        task.error_code = error_code
        task.error_message = error_message
    elif target_status == BackgroundTaskStatus.CANCELLED:
        task.completed_at = changed_at
        task.heartbeat_at = changed_at
        task.cancel_requested = False
    return task


def record_background_task_log(
    db: Session,
    task: BackgroundTask,
    *,
    event: str,
    message: str,
    details: dict | None = None,
) -> BackgroundTaskLog:
    if task.id is None:
        db.flush()
    log = BackgroundTaskLog(
        task_id=task.id,
        event=event,
        message=message,
        status=task.status,
        progress=task.progress,
        details=details or {},
    )
    db.add(log)
    return log


def create_resource_parse_background_task(
    db: Session,
    *,
    parse_task_id: str,
    source_url: str,
    preferred_language: str | None,
) -> BackgroundTask:
    task = BackgroundTask(
        task_type=BackgroundTaskType.RESOURCE_PARSE,
        title=f"解析资源页面：{source_url}",
        status=BackgroundTaskStatus.WAITING,
        max_attempts=1,
        cancellable=False,
        task_payload={
            "parse_task_id": parse_task_id,
            "source_url": source_url,
            "preferred_language": preferred_language,
        },
    )
    db.add(task)
    db.flush()
    record_background_task_log(
        db,
        task,
        event="created",
        message="资源解析任务已创建",
    )
    transition_background_task(task, BackgroundTaskStatus.RUNNING)
    record_background_task_log(
        db,
        task,
        event="started",
        message="资源解析任务开始执行",
    )
    db.commit()
    db.refresh(task)
    return task


def complete_resource_parse_background_task(
    db: Session,
    task: BackgroundTask,
    *,
    title: str,
    source_site: str | None,
    downloads_detected: int,
    subtitles_detected: int,
) -> BackgroundTask:
    task.task_result = {
        "title": title,
        "source_site": source_site,
        "downloads_detected": downloads_detected,
        "subtitles_detected": subtitles_detected,
    }
    transition_background_task(task, BackgroundTaskStatus.COMPLETED)
    record_background_task_log(
        db,
        task,
        event="completed",
        message="资源解析任务执行完成",
        details=task.task_result,
    )
    db.commit()
    db.refresh(task)
    return task


def fail_resource_parse_background_task(
    db: Session,
    task: BackgroundTask,
    exc: Exception,
) -> BackgroundTask:
    transition_background_task(
        task,
        BackgroundTaskStatus.FAILED,
        error_code=getattr(exc, "code", type(exc).__name__),
        error_message=str(exc),
    )
    record_background_task_log(
        db,
        task,
        event="failed",
        message="资源解析任务执行失败",
        details={"error_code": task.error_code, "error_message": task.error_message},
    )
    db.commit()
    db.refresh(task)
    return task


def sync_download_background_task(
    db: Session,
    task: DownloadTask,
) -> BackgroundTask:
    background = db.scalar(
        select(BackgroundTask).where(
            BackgroundTask.task_type == BackgroundTaskType.DOWNLOAD,
            BackgroundTask.source_task_id == task.id,
        )
    )
    if background is None:
        background = BackgroundTask(
            task_type=BackgroundTaskType.DOWNLOAD,
            title=f"下载视频：{task.target_name}",
            source_task_id=task.id,
            max_attempts=100,
            priority=task.priority,
            pause_supported=True,
            cancellable=True,
            task_payload={
                "source_url": task.source_url,
                "target_name": task.target_name,
                "media_id": task.media_id,
                "downloader": task.downloader_name,
            },
        )
        db.add(background)
        db.flush()
        record_background_task_log(
            db,
            background,
            event="created",
            message="视频下载任务已接入统一任务中心",
        )

    previous_status = background.status
    previous_progress = background.progress
    target_status = normalize_task_status(task.status)
    if (
        background.status == BackgroundTaskStatus.FAILED
        and target_status == BackgroundTaskStatus.WAITING
        and background.attempt < background.max_attempts
    ):
        background.attempt += 1
    background.status = target_status
    background.priority = task.priority
    background.progress = task.progress
    background.processed_items = task.downloaded_bytes
    background.total_items = task.total_bytes
    background.error_message = task.error_message
    now = datetime.now()
    if target_status == BackgroundTaskStatus.RUNNING:
        background.started_at = background.started_at or now
        background.heartbeat_at = now
        background.completed_at = None
    elif target_status in {
        BackgroundTaskStatus.COMPLETED,
        BackgroundTaskStatus.FAILED,
        BackgroundTaskStatus.CANCELLED,
    }:
        background.completed_at = now
        background.heartbeat_at = now
    if target_status == BackgroundTaskStatus.COMPLETED:
        background.task_result = {
            "target_path": task.target_path,
            "downloaded_bytes": task.downloaded_bytes,
            "checksum_sha256": task.checksum_sha256,
        }
        background.error_code = None
    elif target_status == BackgroundTaskStatus.FAILED:
        background.error_code = "DOWNLOAD_FAILED"
    else:
        background.error_code = None
    _record_sync_change(
        db,
        background,
        previous_status=previous_status,
        previous_progress=previous_progress,
    )
    return background


def sync_scan_background_task(
    db: Session,
    task: ScanTask,
) -> BackgroundTask:
    background = _get_background_task(
        db,
        task_type=BackgroundTaskType.MEDIA_SCAN,
        source_task_id=task.id,
    )
    if background is None:
        background = BackgroundTask(
            task_type=BackgroundTaskType.MEDIA_SCAN,
            title=f"扫描媒体目录：{task.path}",
            source_task_id=task.id,
            cancellable=False,
            task_payload={
                "path": task.path,
                "media_id": task.media_id,
                "incremental": task.incremental,
            },
        )
        db.add(background)
        db.flush()
        record_background_task_log(
            db,
            background,
            event="created",
            message="本地扫描任务已接入统一任务中心",
        )
    previous_status = background.status
    previous_progress = background.progress
    _sync_common_task_fields(
        background,
        status=normalize_task_status(task.status),
        progress=task.progress,
        processed_items=task.processed_files,
        total_items=task.total_files,
        error_message=task.error_message,
    )
    if background.status == BackgroundTaskStatus.COMPLETED:
        background.task_result = {
            "discovered_files": task.discovered_files,
            "added_files": task.added_files,
            "updated_files": task.updated_files,
            "skipped_files": task.skipped_files,
            "missing_files": task.missing_files,
            "restored_files": task.restored_files,
        }
    elif background.status == BackgroundTaskStatus.FAILED:
        background.error_code = "MEDIA_SCAN_FAILED"
    _record_sync_change(
        db,
        background,
        previous_status=previous_status,
        previous_progress=previous_progress,
    )
    return background


def sync_analysis_background_task(
    db: Session,
    task: AnalysisTask,
) -> BackgroundTask:
    background = _get_background_task(
        db,
        task_type=BackgroundTaskType.MEDIA_ANALYSIS,
        source_task_id=task.id,
    )
    if background is None:
        parent_task_id = None
        attempt = 1
        if task.retry_of_task_id is not None:
            parent = _get_background_task(
                db,
                task_type=BackgroundTaskType.MEDIA_ANALYSIS,
                source_task_id=task.retry_of_task_id,
            )
            if parent is not None:
                parent_task_id = parent.id
                attempt = parent.attempt + 1
        background = BackgroundTask(
            task_type=BackgroundTaskType.MEDIA_ANALYSIS,
            title=f"分析本地视频（{len(task.resource_ids)} 项）",
            source_task_id=task.id,
            parent_task_id=parent_task_id,
            attempt=attempt,
            max_attempts=max(attempt, 100),
            cancellable=False,
            task_payload={
                "resource_ids": task.resource_ids,
                "force": task.force,
                "retry_of_task_id": task.retry_of_task_id,
            },
        )
        db.add(background)
        db.flush()
        record_background_task_log(
            db,
            background,
            event="created",
            message="媒体分析任务已接入统一任务中心",
        )
    previous_status = background.status
    previous_progress = background.progress
    _sync_common_task_fields(
        background,
        status=normalize_task_status(task.status),
        progress=task.progress,
        processed_items=task.processed_resources,
        total_items=task.total_resources,
        error_message=task.error_message,
    )
    if background.status == BackgroundTaskStatus.COMPLETED:
        background.task_result = {
            "analyzed_resource_ids": task.analyzed_resource_ids,
            "skipped_resource_ids": task.skipped_resource_ids,
            "missing_resource_ids": task.missing_resource_ids,
            "failures": task.failures,
        }
    elif background.status == BackgroundTaskStatus.FAILED:
        background.error_code = "MEDIA_ANALYSIS_FAILED"
    _record_sync_change(
        db,
        background,
        previous_status=previous_status,
        previous_progress=previous_progress,
    )
    return background


def sync_hls_background_task(
    db: Session,
    task: HlsTask,
) -> BackgroundTask:
    background = _get_background_task(
        db,
        task_type=BackgroundTaskType.HLS_TRANSCODE,
        source_task_id=task.id,
    )
    if background is None:
        background = BackgroundTask(
            task_type=BackgroundTaskType.HLS_TRANSCODE,
            title=f"HLS 转码：本地资源 {task.resource_id}",
            source_task_id=task.id,
            cancellable=False,
            task_payload={"resource_id": task.resource_id},
        )
        db.add(background)
        db.flush()
        record_background_task_log(
            db,
            background,
            event="created",
            message="HLS 转码任务已接入统一任务中心",
        )
    previous_status = background.status
    previous_progress = background.progress
    _sync_common_task_fields(
        background,
        status=normalize_task_status(task.status),
        progress=task.progress,
        processed_items=0,
        total_items=None,
        error_message=task.error_message,
    )
    if background.status == BackgroundTaskStatus.COMPLETED:
        background.task_result = {
            "resource_id": task.resource_id,
            "output_directory": task.output_directory,
            "playlist_path": task.playlist_path,
        }
    elif background.status == BackgroundTaskStatus.FAILED:
        background.error_code = "HLS_TRANSCODE_FAILED"
    _record_sync_change(
        db,
        background,
        previous_status=previous_status,
        previous_progress=previous_progress,
    )
    return background


def _get_background_task(
    db: Session,
    *,
    task_type: BackgroundTaskType,
    source_task_id: int,
) -> BackgroundTask | None:
    return db.scalar(
        select(BackgroundTask).where(
            BackgroundTask.task_type == task_type,
            BackgroundTask.source_task_id == source_task_id,
        )
    )


def _sync_common_task_fields(
    background: BackgroundTask,
    *,
    status: BackgroundTaskStatus,
    progress: float,
    processed_items: int,
    total_items: int | None,
    error_message: str | None,
) -> None:
    background.status = status
    background.progress = progress
    background.processed_items = processed_items
    background.total_items = total_items
    background.error_message = error_message
    now = datetime.now()
    if status == BackgroundTaskStatus.RUNNING:
        background.started_at = background.started_at or now
        background.heartbeat_at = now
        background.completed_at = None
        background.error_code = None
    elif status in {
        BackgroundTaskStatus.COMPLETED,
        BackgroundTaskStatus.FAILED,
        BackgroundTaskStatus.CANCELLED,
    }:
        background.completed_at = now
        background.heartbeat_at = now
    else:
        background.completed_at = None
        if status == BackgroundTaskStatus.WAITING:
            background.heartbeat_at = None
            background.error_code = None


def _record_sync_change(
    db: Session,
    task: BackgroundTask,
    *,
    previous_status: BackgroundTaskStatus,
    previous_progress: float,
) -> None:
    if task.status != previous_status:
        record_background_task_log(
            db,
            task,
            event=task.status.value,
            message=f"任务状态由 {previous_status.value} 更新为 {task.status.value}",
            details={
                "previous_status": previous_status.value,
                "current_status": task.status.value,
            },
        )
    elif task.progress != previous_progress:
        record_background_task_log(
            db,
            task,
            event="progress",
            message=f"任务进度更新为 {task.progress:.2f}%",
            details={
                "previous_progress": previous_progress,
                "current_progress": task.progress,
                "processed_items": task.processed_items,
                "total_items": task.total_items,
            },
        )
