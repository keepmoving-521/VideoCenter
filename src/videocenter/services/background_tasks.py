from datetime import datetime
from enum import StrEnum

from videocenter.models.background_task import BackgroundTask, BackgroundTaskStatus

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
