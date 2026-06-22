from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from videocenter.models.analysis import AnalysisTask, AnalysisTaskStatus
from videocenter.models.background_task import (
    BackgroundTask,
    BackgroundTaskLog,
    BackgroundTaskStatus,
    BackgroundTaskType,
)
from videocenter.models.download import DownloadStatus
from videocenter.models.hls import HlsTask, HlsTaskStatus
from videocenter.models.scan import ScanTask, ScanTaskStatus
from videocenter.services.background_tasks import (
    record_background_task_log,
    sync_analysis_background_task,
    sync_download_background_task,
    sync_hls_background_task,
    sync_scan_background_task,
)

pytestmark = pytest.mark.integration


def test_list_background_tasks_supports_filters_and_pagination(
    api_client: TestClient,
    db_session: Session,
):
    db_session.add_all(
        [
            BackgroundTask(
                task_type=BackgroundTaskType.MEDIA_SCAN,
                title="Scan",
                status=BackgroundTaskStatus.COMPLETED,
                progress=100,
            ),
            BackgroundTask(
                task_type=BackgroundTaskType.DOWNLOAD,
                title="Download waiting",
            ),
            BackgroundTask(
                task_type=BackgroundTaskType.DOWNLOAD,
                title="Download running",
                status=BackgroundTaskStatus.RUNNING,
                progress=40,
            ),
        ]
    )
    db_session.commit()

    payload = api_client.get(
        "/api/v1/tasks",
        params={
            "task_type": "download",
            "status": "running",
            "page": 1,
            "page_size": 1,
        },
    ).json()

    assert payload["total"] == 1
    assert payload["total_pages"] == 1
    assert payload["items"][0]["title"] == "Download running"
    assert payload["items"][0]["progress"] == 40
    assert payload["items"][0]["task_type"] == "download"
    assert payload["items"][0]["status"] == "running"


def test_get_background_task_returns_progress_and_result(
    api_client: TestClient,
    db_session: Session,
):
    task = BackgroundTask(
        task_type=BackgroundTaskType.MEDIA_ANALYSIS,
        title="Analyze",
        status=BackgroundTaskStatus.COMPLETED,
        progress=100,
        processed_items=2,
        total_items=2,
        task_result={"analyzed_resource_ids": [1, 2]},
    )
    db_session.add(task)
    db_session.commit()

    response = api_client.get(f"/api/v1/tasks/{task.id}")

    assert response.status_code == 200
    assert response.json()["processed_items"] == 2
    assert response.json()["total_items"] == 2
    assert response.json()["task_result"] == {"analyzed_resource_ids": [1, 2]}


def test_cancel_download_background_task_dispatches_to_download(
    api_client: TestClient,
    db_session: Session,
    model_factory,
    monkeypatch,
):
    class FakeQueue:
        @staticmethod
        def cancel(task_id: int) -> bool:
            return task_id > 0

    monkeypatch.setattr(
        "videocenter.services.downloads.get_download_queue",
        lambda: FakeQueue(),
    )
    download = model_factory.download_task(status=DownloadStatus.WAITING)
    background = sync_download_background_task(db_session, download)
    db_session.commit()

    response = api_client.post(f"/api/v1/tasks/{background.id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    db_session.refresh(download)
    assert download.status == DownloadStatus.CANCELLED
    assert api_client.post(f"/api/v1/tasks/{background.id}/cancel").status_code == 200


@pytest.mark.parametrize(
    ("task_type", "status", "cancellable", "code"),
    [
        (
            BackgroundTaskType.MEDIA_SCAN,
            BackgroundTaskStatus.RUNNING,
            False,
            "BACKGROUND_TASK_NOT_CANCELLABLE",
        ),
        (
            BackgroundTaskType.GENERIC,
            BackgroundTaskStatus.RUNNING,
            True,
            "BACKGROUND_TASK_CANCEL_NOT_SUPPORTED",
        ),
        (
            BackgroundTaskType.DOWNLOAD,
            BackgroundTaskStatus.COMPLETED,
            True,
            "BACKGROUND_TASK_NOT_CANCELLABLE",
        ),
    ],
)
def test_cancel_background_task_rejects_unsupported_state_or_type(
    api_client: TestClient,
    api_assertions,
    db_session: Session,
    task_type: BackgroundTaskType,
    status: BackgroundTaskStatus,
    cancellable: bool,
    code: str,
):
    task = BackgroundTask(
        task_type=task_type,
        title="Task",
        status=status,
        cancellable=cancellable,
    )
    db_session.add(task)
    db_session.commit()

    api_assertions.assert_error(
        api_client.post(f"/api/v1/tasks/{task.id}/cancel"),
        status_code=409,
        code=code,
    )


def test_background_task_api_validates_and_handles_missing_task(
    api_client: TestClient,
    api_assertions,
):
    api_assertions.assert_validation_error(
        api_client.get("/api/v1/tasks", params={"page_size": 201}),
        ["query", "page_size"],
    )
    api_assertions.assert_error(
        api_client.get("/api/v1/tasks/999999"),
        status_code=404,
        code="BACKGROUND_TASK_NOT_FOUND",
    )
    api_assertions.assert_error(
        api_client.post("/api/v1/tasks/999999/cancel"),
        status_code=404,
        code="BACKGROUND_TASK_NOT_FOUND",
    )


def test_background_task_logs_are_queryable_and_filterable(
    api_client: TestClient,
    db_session: Session,
):
    task = BackgroundTask(
        task_type=BackgroundTaskType.GENERIC,
        title="Logged task",
    )
    db_session.add(task)
    db_session.flush()
    record_background_task_log(
        db_session,
        task,
        event="created",
        message="Task created",
    )
    task.status = BackgroundTaskStatus.FAILED
    task.progress = 30
    record_background_task_log(
        db_session,
        task,
        event="failed",
        message="Task failed",
        details={"reason": "boom"},
    )
    db_session.commit()

    payload = api_client.get(f"/api/v1/tasks/{task.id}/logs").json()
    failed = api_client.get(
        f"/api/v1/tasks/{task.id}/logs",
        params={"event": "failed"},
    ).json()

    assert payload["total"] == 2
    assert payload["items"][0]["event"] == "failed"
    assert payload["items"][0]["progress"] == 30
    assert failed["total"] == 1
    assert failed["items"][0]["details"] == {"reason": "boom"}


def test_retry_failed_download_task(
    api_client: TestClient,
    db_session: Session,
    model_factory,
    monkeypatch,
):
    class FakeQueue:
        @staticmethod
        def enqueue(task_id: int, *, priority: int = 0) -> bool:
            return task_id > 0 and priority >= -100

    monkeypatch.setattr(
        "videocenter.services.downloads.get_download_queue",
        lambda: FakeQueue(),
    )
    download = model_factory.download_task(
        status=DownloadStatus.FAILED,
        error_message="network failed",
    )
    background = sync_download_background_task(db_session, download)
    db_session.commit()

    response = api_client.post(f"/api/v1/tasks/{background.id}/retry")

    assert response.status_code == 200
    assert response.json()["status"] == "waiting"
    assert response.json()["attempt"] == 2
    db_session.refresh(download)
    assert download.status == DownloadStatus.WAITING
    logs = api_client.get(
        f"/api/v1/tasks/{background.id}/logs",
        params={"event": "retry"},
    ).json()
    assert logs["total"] == 1


@pytest.mark.parametrize(
    "task_type",
    [
        BackgroundTaskType.MEDIA_SCAN,
        BackgroundTaskType.HLS_TRANSCODE,
    ],
)
def test_retry_failed_scan_and_hls_task(
    api_client: TestClient,
    db_session: Session,
    model_factory,
    monkeypatch,
    task_type: BackgroundTaskType,
):
    started: list[int] = []
    if task_type == BackgroundTaskType.MEDIA_SCAN:
        source = ScanTask(
            path="D:/Media",
            status=ScanTaskStatus.FAILED,
            error_message="scan failed",
        )
        db_session.add(source)
        db_session.flush()
        background = sync_scan_background_task(db_session, source)
        monkeypatch.setattr(
            "videocenter.api.routes.tasks.start_scan_task",
            started.append,
        )
    else:
        resource = model_factory.local_resource()
        source = HlsTask(
            resource_id=resource.id,
            status=HlsTaskStatus.FAILED,
            error_message="ffmpeg failed",
        )
        db_session.add(source)
        db_session.flush()
        background = sync_hls_background_task(db_session, source)
        monkeypatch.setattr(
            "videocenter.api.routes.tasks.start_hls_task",
            started.append,
        )
    db_session.commit()

    response = api_client.post(f"/api/v1/tasks/{background.id}/retry")

    assert response.status_code == 200
    assert response.json()["status"] == "waiting"
    assert response.json()["attempt"] == 2
    assert started == [source.id]


def test_retry_failed_analysis_returns_child_background_task(
    api_client: TestClient,
    db_session: Session,
    model_factory,
    monkeypatch,
):
    resource = model_factory.local_resource()
    source = AnalysisTask(
        resource_ids=[resource.id],
        status=AnalysisTaskStatus.FAILED,
        total_resources=1,
        processed_resources=0,
        error_message="analysis crashed",
    )
    db_session.add(source)
    db_session.flush()
    original = sync_analysis_background_task(db_session, source)
    db_session.commit()
    started: list[int] = []
    monkeypatch.setattr(
        "videocenter.api.routes.tasks.start_analysis_task",
        started.append,
    )

    response = api_client.post(f"/api/v1/tasks/{original.id}/retry")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] != original.id
    assert payload["status"] == "waiting"
    assert payload["parent_task_id"] == original.id
    assert payload["attempt"] == 2
    assert started == [payload["source_task_id"]]


def test_retry_rejects_non_failed_and_unsupported_tasks(
    api_client: TestClient,
    api_assertions,
    db_session: Session,
):
    waiting = BackgroundTask(
        task_type=BackgroundTaskType.DOWNLOAD,
        title="Waiting",
    )
    parsing = BackgroundTask(
        task_type=BackgroundTaskType.RESOURCE_PARSE,
        title="Parse failed",
        status=BackgroundTaskStatus.FAILED,
        source_task_id=1,
    )
    db_session.add_all([waiting, parsing])
    db_session.commit()

    api_assertions.assert_error(
        api_client.post(f"/api/v1/tasks/{waiting.id}/retry"),
        status_code=409,
        code="BACKGROUND_TASK_NOT_RETRYABLE",
    )
    api_assertions.assert_error(
        api_client.post(f"/api/v1/tasks/{parsing.id}/retry"),
        status_code=409,
        code="BACKGROUND_TASK_RETRY_NOT_SUPPORTED",
    )


def test_cleanup_removes_only_expired_finished_tasks_and_logs(
    api_client: TestClient,
    db_session: Session,
):
    old_time = datetime.now() - timedelta(days=31)
    old = BackgroundTask(
        task_type=BackgroundTaskType.GENERIC,
        title="Old completed",
        status=BackgroundTaskStatus.COMPLETED,
        progress=100,
        completed_at=old_time,
    )
    recent = BackgroundTask(
        task_type=BackgroundTaskType.GENERIC,
        title="Recent completed",
        status=BackgroundTaskStatus.COMPLETED,
        progress=100,
        completed_at=datetime.now(),
    )
    active = BackgroundTask(
        task_type=BackgroundTaskType.GENERIC,
        title="Active",
        status=BackgroundTaskStatus.RUNNING,
        completed_at=old_time,
    )
    db_session.add_all([old, recent, active])
    db_session.flush()
    db_session.add_all(
        [
            BackgroundTaskLog(
                task_id=old.id,
                event="completed",
                message="old log",
            ),
            BackgroundTaskLog(
                task_id=recent.id,
                event="completed",
                message="recent log",
            ),
        ]
    )
    db_session.commit()
    old_id = old.id
    recent_id = recent.id
    active_id = active.id

    payload = api_client.post(
        "/api/v1/tasks/cleanup",
        json={"max_age_days": 30},
    ).json()

    assert payload == {
        "deleted_task_count": 1,
        "deleted_task_ids": [old_id],
        "deleted_log_count": 1,
    }
    db_session.expire_all()
    assert db_session.get(BackgroundTask, old_id) is None
    assert db_session.get(BackgroundTask, recent_id) is not None
    assert db_session.get(BackgroundTask, active_id) is not None
