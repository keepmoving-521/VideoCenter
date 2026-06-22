from datetime import datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.models.background_task import (
    BackgroundTask,
    BackgroundTaskStatus,
    BackgroundTaskType,
)
from videocenter.models.download import DownloadTask

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
    transition_background_task(task, BackgroundTaskStatus.RUNNING)
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
    return background
