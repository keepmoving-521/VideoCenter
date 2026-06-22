from dataclasses import dataclass

from sqlalchemy import select

from videocenter.core.database import SessionLocal
from videocenter.models.analysis import AnalysisTask
from videocenter.models.background_task import (
    BackgroundTask,
    BackgroundTaskStatus,
    BackgroundTaskType,
)
from videocenter.models.download import DownloadTask
from videocenter.models.hls import HlsTask
from videocenter.models.scan import ScanTask
from videocenter.services.analysis_tasks import restore_analysis_tasks
from videocenter.services.background_tasks import (
    record_background_task_log,
    sync_analysis_background_task,
    sync_download_background_task,
    sync_hls_background_task,
    sync_scan_background_task,
    transition_background_task,
)
from videocenter.services.downloads import restore_download_queue
from videocenter.services.hls import restore_hls_tasks
from videocenter.services.local_library import restore_scan_tasks


@dataclass(frozen=True, slots=True)
class TaskRecoveryReport:
    restored_downloads: int
    restored_scans: int
    restored_analyses: int
    restored_hls: int
    reconciled_tasks: int
    interrupted_tasks: int

    @property
    def restored_total(self) -> int:
        return (
            self.restored_downloads
            + self.restored_scans
            + self.restored_analyses
            + self.restored_hls
        )


def recover_background_tasks() -> TaskRecoveryReport:
    reconciled_tasks, interrupted_tasks = _audit_running_background_tasks()
    return TaskRecoveryReport(
        restored_downloads=restore_download_queue(),
        restored_scans=restore_scan_tasks(),
        restored_analyses=restore_analysis_tasks(),
        restored_hls=restore_hls_tasks(),
        reconciled_tasks=reconciled_tasks,
        interrupted_tasks=interrupted_tasks,
    )


def _audit_running_background_tasks() -> tuple[int, int]:
    reconciled = 0
    interrupted = 0
    with SessionLocal() as db:
        tasks = db.scalars(
            select(BackgroundTask).where(BackgroundTask.status == BackgroundTaskStatus.RUNNING)
        ).all()
        for task in tasks:
            source = _sync_from_source(db, task)
            if source:
                reconciled += 1
                record_background_task_log(
                    db,
                    task,
                    event="recovery_audit",
                    message="应用重启时已根据业务任务修复统一任务状态",
                    details={"task_type": task.task_type.value},
                )
                continue
            transition_background_task(
                task,
                BackgroundTaskStatus.FAILED,
                error_code="TASK_INTERRUPTED_BY_RESTART",
                error_message="应用重启中断任务，且任务无法自动恢复",
            )
            record_background_task_log(
                db,
                task,
                event="recovery_failed",
                message="应用重启后任务无法自动恢复",
                details={
                    "task_type": task.task_type.value,
                    "source_task_id": task.source_task_id,
                },
            )
            interrupted += 1
        db.commit()
    return reconciled, interrupted


def _sync_from_source(db, task: BackgroundTask) -> bool:
    if task.source_task_id is None:
        return False
    if task.task_type == BackgroundTaskType.DOWNLOAD:
        source = db.get(DownloadTask, task.source_task_id)
        if source is not None:
            sync_download_background_task(db, source)
            return True
    elif task.task_type == BackgroundTaskType.MEDIA_SCAN:
        source = db.get(ScanTask, task.source_task_id)
        if source is not None:
            sync_scan_background_task(db, source)
            return True
    elif task.task_type == BackgroundTaskType.MEDIA_ANALYSIS:
        source = db.get(AnalysisTask, task.source_task_id)
        if source is not None:
            sync_analysis_background_task(db, source)
            return True
    elif task.task_type == BackgroundTaskType.HLS_TRANSCODE:
        source = db.get(HlsTask, task.source_task_id)
        if source is not None:
            sync_hls_background_task(db, source)
            return True
    return False
