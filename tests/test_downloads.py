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
                )
            )
        return DownloadResult(
            target_path=request.target_path.resolve(),
            file_size=10,
            mime_type="video/mp4",
        )


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
    assert queued_ids == [response.json()["id"]]
