import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.models.download import DownloadStatus
from videocenter.models.media import LocalResource
from videocenter.services.downloaders import (
    DownloadCancellationToken,
    Downloader,
    DownloadProgress,
    DownloadProgressState,
    DownloadResult,
)
from videocenter.services.downloads import _run_download, safe_target_name


class FakeDownloader(Downloader):
    name = "fake"

    def download(
        self,
        request,
        *,
        progress_callback=None,
        cancellation_token=None,
    ):
        if progress_callback is not None:
            progress_callback(
                DownloadProgress(
                    state=DownloadProgressState.DOWNLOADING,
                    downloaded_bytes=5,
                    total_bytes=10,
                    speed_bytes_per_second=2,
                )
            )
        return DownloadResult(
            target_path=request.target_path.resolve(),
            file_size=10,
            mime_type="video/mp4",
        )


class StubDownloadQueue:
    def __init__(self) -> None:
        self.queued: list[int] = []
        self.paused: set[int] = set()
        self.running: set[int] = set()

    def enqueue(self, task_id: int) -> bool:
        self.queued.append(task_id)
        return True

    def pause(self, task_id: int) -> bool:
        self.paused.add(task_id)
        return True

    def resume(self, task_id: int) -> bool:
        if task_id not in self.paused:
            return False
        self.paused.remove(task_id)
        return True

    def cancel(self, task_id: int) -> bool:
        return True

    def is_running(self, task_id: int) -> bool:
        return task_id in self.running


def test_safe_target_name_removes_unsafe_characters():
    assert safe_target_name("../my:video?.mp4") == "my_video_.mp4"


def test_safe_target_name_rejects_empty_name():
    with pytest.raises(ValueError):
        safe_target_name("...")


def test_download_task_execution_uses_downloader_result(
    db_session: Session,
    model_factory,
):
    media = model_factory.media(title="Download Target")
    task = model_factory.download_task(
        media=media,
        target_name="contract-video.mp4",
    )
    assert task.status == DownloadStatus.WAITING

    _run_download(
        task.id,
        DownloadCancellationToken(),
        downloader=FakeDownloader(),
    )

    db_session.expire_all()
    completed_task = db_session.get(type(task), task.id)
    assert completed_task.status == DownloadStatus.COMPLETED
    assert completed_task.progress == 100
    assert completed_task.downloaded_bytes == 10
    assert completed_task.total_bytes == 10
    assert completed_task.speed_bytes_per_second == 2
    assert completed_task.remaining_seconds == 0
    assert completed_task.target_path.endswith("contract-video.mp4")
    resource = db_session.scalar(select(LocalResource).where(LocalResource.media_id == media.id))
    assert resource is not None
    assert resource.file_size == 10
    assert resource.mime_type == "video/mp4"


def test_created_download_task_starts_in_waiting_status(
    api_client: TestClient,
    monkeypatch,
):
    queued_ids: list[int] = []
    monkeypatch.setattr(
        "videocenter.api.routes.downloads.start_download",
        queued_ids.append,
    )

    response = api_client.post(
        "/api/v1/downloads",
        json={
            "source_url": "https://example.com/video.mp4",
            "target_name": "video.mp4",
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "waiting"
    assert response.json()["progress"] == 0
    assert response.json()["downloaded_bytes"] == 0
    assert response.json()["total_bytes"] is None
    assert response.json()["speed_bytes_per_second"] is None
    assert response.json()["remaining_seconds"] is None
    assert queued_ids == [response.json()["id"]]


def test_download_pause_resume_cancel_and_retry_api(
    api_client: TestClient,
    api_assertions,
    db_session: Session,
    model_factory,
    monkeypatch,
):
    task_queue = StubDownloadQueue()
    monkeypatch.setattr(
        "videocenter.services.downloads.get_download_queue",
        lambda: task_queue,
    )
    task = model_factory.download_task(
        status=DownloadStatus.DOWNLOADING,
        progress=50,
        downloaded_bytes=500,
        total_bytes=1000,
        speed_bytes_per_second=100,
        remaining_seconds=5,
    )

    paused = api_assertions.assert_status(
        api_client.post(f"/api/v1/downloads/{task.id}/pause"),
        200,
    )
    assert paused["status"] == "paused"
    assert paused["speed_bytes_per_second"] is None
    assert paused["remaining_seconds"] is None

    task_queue.running.add(task.id)
    resumed = api_assertions.assert_status(
        api_client.post(f"/api/v1/downloads/{task.id}/resume"),
        200,
    )
    assert resumed["status"] == "downloading"

    cancelled = api_assertions.assert_status(
        api_client.post(f"/api/v1/downloads/{task.id}/cancel"),
        200,
    )
    assert cancelled["status"] == "cancelled"

    db_session.expire_all()
    failed_task = model_factory.download_task(
        status=DownloadStatus.FAILED,
        progress=75,
        downloaded_bytes=750,
        total_bytes=1000,
        speed_bytes_per_second=None,
        remaining_seconds=None,
        error_message="network failed",
        target_path="data/media/failed.mp4",
    )
    retried = api_assertions.assert_status(
        api_client.post(f"/api/v1/downloads/{failed_task.id}/retry"),
        200,
    )
    assert retried["status"] == "waiting"
    assert retried["progress"] == 0
    assert retried["downloaded_bytes"] == 0
    assert retried["total_bytes"] is None
    assert retried["error_message"] is None
    assert failed_task.id in task_queue.queued


@pytest.mark.parametrize(
    ("status", "action", "error_code"),
    [
        (DownloadStatus.COMPLETED, "pause", "DOWNLOAD_NOT_PAUSABLE"),
        (DownloadStatus.WAITING, "resume", "DOWNLOAD_NOT_RESUMABLE"),
        (DownloadStatus.COMPLETED, "cancel", "DOWNLOAD_NOT_CANCELLABLE"),
        (DownloadStatus.CANCELLED, "retry", "DOWNLOAD_NOT_RETRYABLE"),
    ],
)
def test_download_actions_reject_invalid_states(
    api_client: TestClient,
    api_assertions,
    model_factory,
    monkeypatch,
    status,
    action,
    error_code,
):
    monkeypatch.setattr(
        "videocenter.services.downloads.get_download_queue",
        lambda: StubDownloadQueue(),
    )
    task = model_factory.download_task(status=status)

    api_assertions.assert_error(
        api_client.post(f"/api/v1/downloads/{task.id}/{action}"),
        status_code=409,
        code=error_code,
    )
