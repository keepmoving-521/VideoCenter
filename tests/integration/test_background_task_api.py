import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from videocenter.models.background_task import (
    BackgroundTask,
    BackgroundTaskStatus,
    BackgroundTaskType,
)
from videocenter.models.download import DownloadStatus
from videocenter.services.background_tasks import sync_download_background_task

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
