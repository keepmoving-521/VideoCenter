from datetime import datetime

import pytest

from videocenter.models.analysis import AnalysisTaskStatus
from videocenter.models.background_task import (
    BackgroundTask,
    BackgroundTaskStatus,
    BackgroundTaskType,
)
from videocenter.models.download import DownloadStatus
from videocenter.models.hls import HlsTaskStatus
from videocenter.models.scan import ScanTaskStatus
from videocenter.services.background_tasks import (
    InvalidTaskStatusTransition,
    allowed_target_statuses,
    can_transition_task_status,
    normalize_task_status,
    transition_background_task,
)


def make_task(**overrides) -> BackgroundTask:
    values = {
        "task_type": BackgroundTaskType.GENERIC,
        "title": "Test task",
        "status": BackgroundTaskStatus.WAITING,
    }
    values.update(overrides)
    return BackgroundTask(**values)


@pytest.mark.parametrize(
    ("legacy_status", "expected"),
    [
        (DownloadStatus.DOWNLOADING, BackgroundTaskStatus.RUNNING),
        (DownloadStatus.PAUSED, BackgroundTaskStatus.PAUSED),
        (ScanTaskStatus.RUNNING, BackgroundTaskStatus.RUNNING),
        (AnalysisTaskStatus.FAILED, BackgroundTaskStatus.FAILED),
        (HlsTaskStatus.COMPLETED, BackgroundTaskStatus.COMPLETED),
        ("cancelled", BackgroundTaskStatus.CANCELLED),
    ],
)
def test_normalize_existing_task_statuses(legacy_status, expected):
    assert normalize_task_status(legacy_status) == expected


def test_status_categories_and_allowed_targets():
    assert BackgroundTaskStatus.COMPLETED.is_terminal is True
    assert BackgroundTaskStatus.CANCELLED.is_terminal is True
    assert BackgroundTaskStatus.FAILED.is_terminal is False
    assert BackgroundTaskStatus.RUNNING.is_active is True
    assert BackgroundTaskStatus.COMPLETED.is_successful is True
    assert allowed_target_statuses(BackgroundTaskStatus.WAITING) == {
        BackgroundTaskStatus.RUNNING,
        BackgroundTaskStatus.CANCELLED,
    }
    assert can_transition_task_status(
        BackgroundTaskStatus.RUNNING,
        BackgroundTaskStatus.RUNNING,
    )


def test_transition_task_through_normal_success_path():
    started_at = datetime(2026, 6, 22, 1, 0)
    completed_at = datetime(2026, 6, 22, 1, 5)
    task = make_task(total_items=10)

    transition_background_task(
        task,
        BackgroundTaskStatus.RUNNING,
        worker_id="worker-1",
        now=started_at,
    )
    assert task.started_at == started_at
    assert task.worker_id == "worker-1"
    assert task.heartbeat_at == started_at

    transition_background_task(
        task,
        BackgroundTaskStatus.COMPLETED,
        now=completed_at,
    )
    assert task.progress == 100
    assert task.processed_items == 10
    assert task.completed_at == completed_at
    assert task.error_message is None


def test_pause_requires_capability_and_can_resume():
    task = make_task(status=BackgroundTaskStatus.RUNNING)
    with pytest.raises(InvalidTaskStatusTransition):
        transition_background_task(task, BackgroundTaskStatus.PAUSED)

    task.pause_supported = True
    transition_background_task(task, BackgroundTaskStatus.PAUSED)
    transition_background_task(
        task,
        BackgroundTaskStatus.RUNNING,
        worker_id="worker-2",
    )
    assert task.status == BackgroundTaskStatus.RUNNING
    assert task.worker_id == "worker-2"


def test_failed_task_retry_increments_attempt_and_clears_error():
    task = make_task(
        status=BackgroundTaskStatus.RUNNING,
        attempt=1,
        max_attempts=2,
    )
    transition_background_task(
        task,
        BackgroundTaskStatus.FAILED,
        error_code="WORKER_ERROR",
        error_message="boom",
    )
    transition_background_task(task, BackgroundTaskStatus.WAITING)

    assert task.attempt == 2
    assert task.error_code is None
    assert task.error_message is None
    assert task.completed_at is None

    transition_background_task(task, BackgroundTaskStatus.RUNNING)
    transition_background_task(task, BackgroundTaskStatus.FAILED)
    with pytest.raises(InvalidTaskStatusTransition):
        transition_background_task(task, BackgroundTaskStatus.WAITING)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (BackgroundTaskStatus.WAITING, BackgroundTaskStatus.COMPLETED),
        (BackgroundTaskStatus.COMPLETED, BackgroundTaskStatus.RUNNING),
        (BackgroundTaskStatus.CANCELLED, BackgroundTaskStatus.WAITING),
    ],
)
def test_invalid_status_transitions_are_rejected(current, target):
    task = make_task(status=current)
    with pytest.raises(InvalidTaskStatusTransition):
        transition_background_task(task, target)


def test_cancel_requires_capability_and_same_status_is_idempotent():
    task = make_task(cancellable=False)
    with pytest.raises(InvalidTaskStatusTransition):
        transition_background_task(task, BackgroundTaskStatus.CANCELLED)

    original = transition_background_task(task, BackgroundTaskStatus.WAITING)
    assert original is task
