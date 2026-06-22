from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.models.background_task import (
    BackgroundTask,
    BackgroundTaskLog,
    BackgroundTaskStatus,
    BackgroundTaskType,
)
from videocenter.models.download import DownloadStatus
from videocenter.services.background_tasks import sync_download_background_task
from videocenter.services.task_recovery import recover_background_tasks


def test_recovery_reconciles_business_task_before_queue_restore(
    db_session: Session,
    model_factory,
    monkeypatch,
):
    download = model_factory.download_task(status=DownloadStatus.WAITING)
    background = sync_download_background_task(db_session, download)
    background.status = BackgroundTaskStatus.RUNNING
    db_session.commit()
    calls: list[str] = []
    monkeypatch.setattr(
        "videocenter.services.task_recovery.restore_download_queue",
        lambda: calls.append("download") or 1,
    )
    monkeypatch.setattr(
        "videocenter.services.task_recovery.restore_scan_tasks",
        lambda: calls.append("scan") or 2,
    )
    monkeypatch.setattr(
        "videocenter.services.task_recovery.restore_analysis_tasks",
        lambda: calls.append("analysis") or 3,
    )
    monkeypatch.setattr(
        "videocenter.services.task_recovery.restore_hls_tasks",
        lambda: calls.append("hls") or 4,
    )

    report = recover_background_tasks()

    db_session.expire_all()
    recovered = db_session.get(BackgroundTask, background.id)
    assert recovered.status == BackgroundTaskStatus.WAITING
    assert report.restored_total == 10
    assert report.reconciled_tasks == 1
    assert report.interrupted_tasks == 0
    assert calls == ["download", "scan", "analysis", "hls"]
    log = db_session.scalar(
        select(BackgroundTaskLog).where(
            BackgroundTaskLog.task_id == background.id,
            BackgroundTaskLog.event == "recovery_audit",
        )
    )
    assert log is not None


def test_recovery_marks_unrecoverable_running_tasks_failed(
    db_session: Session,
    monkeypatch,
):
    parsing = BackgroundTask(
        task_type=BackgroundTaskType.RESOURCE_PARSE,
        title="Interrupted parse",
        status=BackgroundTaskStatus.RUNNING,
        cancellable=False,
    )
    missing_source = BackgroundTask(
        task_type=BackgroundTaskType.MEDIA_SCAN,
        title="Missing scan",
        status=BackgroundTaskStatus.RUNNING,
        source_task_id=999999,
        cancellable=False,
    )
    db_session.add_all([parsing, missing_source])
    db_session.commit()
    for name in (
        "restore_download_queue",
        "restore_scan_tasks",
        "restore_analysis_tasks",
        "restore_hls_tasks",
    ):
        monkeypatch.setattr(f"videocenter.services.task_recovery.{name}", lambda: 0)

    report = recover_background_tasks()

    db_session.expire_all()
    for task_id in (parsing.id, missing_source.id):
        task = db_session.get(BackgroundTask, task_id)
        assert task.status == BackgroundTaskStatus.FAILED
        assert task.error_code == "TASK_INTERRUPTED_BY_RESTART"
        assert task.completed_at is not None
        log = db_session.scalar(
            select(BackgroundTaskLog).where(
                BackgroundTaskLog.task_id == task_id,
                BackgroundTaskLog.event == "recovery_failed",
            )
        )
        assert log is not None
    assert report.reconciled_tasks == 0
    assert report.interrupted_tasks == 2
