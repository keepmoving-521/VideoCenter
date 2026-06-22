from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.models.background_task import (
    BackgroundTask,
    BackgroundTaskStatus,
    BackgroundTaskType,
)
from videocenter.models.download import DownloadStatus
from videocenter.services.background_tasks import sync_download_background_task


def test_download_task_sync_is_idempotent(db_session: Session, model_factory):
    download = model_factory.download_task(priority=7)

    first = sync_download_background_task(db_session, download)
    second = sync_download_background_task(db_session, download)
    db_session.commit()

    assert first.id == second.id
    assert first.task_type == BackgroundTaskType.DOWNLOAD
    assert first.source_task_id == download.id
    assert first.status == BackgroundTaskStatus.WAITING
    assert first.priority == 7
    assert first.pause_supported is True
    assert first.task_payload["source_url"] == download.source_url
    assert len(db_session.scalars(select(BackgroundTask)).all()) == 1


def test_download_task_sync_tracks_progress_and_completion(
    db_session: Session,
    model_factory,
):
    download = model_factory.download_task()
    background = sync_download_background_task(db_session, download)

    download.status = DownloadStatus.DOWNLOADING
    download.progress = 40
    download.downloaded_bytes = 400
    download.total_bytes = 1000
    sync_download_background_task(db_session, download)
    assert background.status == BackgroundTaskStatus.RUNNING
    assert background.progress == 40
    assert background.processed_items == 400
    assert background.total_items == 1000
    assert background.started_at is not None
    assert background.heartbeat_at is not None

    download.status = DownloadStatus.COMPLETED
    download.progress = 100
    download.downloaded_bytes = 1000
    download.target_path = "D:/Media/video.mp4"
    download.checksum_sha256 = "a" * 64
    sync_download_background_task(db_session, download)
    db_session.commit()

    assert background.status == BackgroundTaskStatus.COMPLETED
    assert background.completed_at is not None
    assert background.task_result == {
        "target_path": "D:/Media/video.mp4",
        "downloaded_bytes": 1000,
        "checksum_sha256": "a" * 64,
    }


def test_download_task_sync_tracks_pause_retry_cancel_and_failure(
    db_session: Session,
    model_factory,
):
    download = model_factory.download_task()
    background = sync_download_background_task(db_session, download)

    download.status = DownloadStatus.PAUSED
    sync_download_background_task(db_session, download)
    assert background.status == BackgroundTaskStatus.PAUSED

    download.status = DownloadStatus.FAILED
    download.error_message = "network failed"
    sync_download_background_task(db_session, download)
    assert background.status == BackgroundTaskStatus.FAILED
    assert background.error_code == "DOWNLOAD_FAILED"

    download.status = DownloadStatus.WAITING
    download.error_message = None
    sync_download_background_task(db_session, download)
    assert background.status == BackgroundTaskStatus.WAITING
    assert background.attempt == 2

    download.status = DownloadStatus.CANCELLED
    sync_download_background_task(db_session, download)
    assert background.status == BackgroundTaskStatus.CANCELLED
