import logging
import threading
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from videocenter.core.database import SessionLocal
from videocenter.core.exceptions import ConflictError
from videocenter.models.analysis import AnalysisTask, AnalysisTaskStatus
from videocenter.models.media import LocalResource
from videocenter.services.local_resource_analysis import analyze_local_resource

logger = logging.getLogger(__name__)
_analysis_threads: dict[int, threading.Thread] = {}
_analysis_lock = threading.Lock()


def create_analysis_task(
    db: Session,
    *,
    resource_ids: list[int],
    force: bool,
    retry_of_task_id: int | None = None,
) -> AnalysisTask:
    task = AnalysisTask(
        retry_of_task_id=retry_of_task_id,
        resource_ids=resource_ids,
        force=force,
        total_resources=len(resource_ids),
        status=AnalysisTaskStatus.WAITING,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def start_analysis_task(task_id: int) -> None:
    thread = threading.Thread(
        target=run_analysis_task,
        args=(task_id,),
        name=f"videocenter-analysis-{task_id}",
        daemon=True,
    )
    with _analysis_lock:
        _analysis_threads[task_id] = thread
    thread.start()


def run_analysis_task(task_id: int) -> None:
    try:
        with SessionLocal() as db:
            task = db.get(AnalysisTask, task_id)
            if task is None:
                return
            task.status = AnalysisTaskStatus.RUNNING
            task.started_at = datetime.now()
            task.error_message = None
            db.commit()

            for index, resource_id in enumerate(task.resource_ids, start=1):
                _process_analysis_resource(db, task, resource_id)
                task.processed_resources = index
                task.progress = round(index / task.total_resources * 100, 2)
                db.commit()

            task.progress = 100
            task.status = AnalysisTaskStatus.COMPLETED
            task.completed_at = datetime.now()
            db.commit()
    except Exception as exc:
        with SessionLocal() as db:
            task = db.get(AnalysisTask, task_id)
            if task is not None:
                task.status = AnalysisTaskStatus.FAILED
                task.error_message = str(exc)
                task.completed_at = datetime.now()
                db.commit()
        logger.exception("Video analysis task failed", extra={"analysis_task_id": task_id})
    finally:
        with _analysis_lock:
            _analysis_threads.pop(task_id, None)


def _process_analysis_resource(
    db: Session,
    task: AnalysisTask,
    resource_id: int,
) -> None:
    resource = db.get(LocalResource, resource_id)
    if resource is None:
        task.missing_resource_ids = [*task.missing_resource_ids, resource_id]
        return
    try:
        with db.begin_nested():
            result = analyze_local_resource(resource, force=task.force)
    except Exception as exc:
        task.failures = [
            *task.failures,
            {"resource_id": resource_id, "error": str(exc)},
        ]
        return
    if result == "analyzed":
        task.analyzed_resource_ids = [*task.analyzed_resource_ids, resource_id]
    elif result == "skipped":
        task.skipped_resource_ids = [*task.skipped_resource_ids, resource_id]
    else:
        task.missing_resource_ids = [*task.missing_resource_ids, resource_id]


def retry_analysis_task(db: Session, task: AnalysisTask) -> AnalysisTask:
    retryable_ids = [failure["resource_id"] for failure in task.failures]
    if task.status == AnalysisTaskStatus.FAILED:
        retryable_ids.extend(task.resource_ids[task.processed_resources :])
    retryable_ids = list(dict.fromkeys(retryable_ids))
    if not retryable_ids:
        raise ConflictError(
            "分析任务没有可重试的失败资源",
            code="ANALYSIS_TASK_NOT_RETRYABLE",
        )
    return create_analysis_task(
        db,
        resource_ids=retryable_ids,
        force=True,
        retry_of_task_id=task.id,
    )


def restore_analysis_tasks() -> int:
    with SessionLocal() as db:
        result = db.execute(
            update(AnalysisTask)
            .where(
                AnalysisTask.status.in_([AnalysisTaskStatus.WAITING, AnalysisTaskStatus.RUNNING])
            )
            .values(
                status=AnalysisTaskStatus.WAITING,
                progress=0,
                processed_resources=0,
                analyzed_resource_ids=[],
                skipped_resource_ids=[],
                missing_resource_ids=[],
                failures=[],
                error_message=None,
                started_at=None,
                completed_at=None,
            )
        )
        task_ids = db.scalars(
            select(AnalysisTask.id)
            .where(AnalysisTask.status == AnalysisTaskStatus.WAITING)
            .order_by(AnalysisTask.id)
        ).all()
        db.commit()
    for task_id in task_ids:
        start_analysis_task(task_id)
    return result.rowcount or 0
