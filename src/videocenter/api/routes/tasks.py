import asyncio
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Path,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from videocenter.core.database import get_db
from videocenter.core.exceptions import ConflictError, NotFoundError
from videocenter.models.analysis import AnalysisTask
from videocenter.models.background_task import (
    BackgroundTask,
    BackgroundTaskLog,
    BackgroundTaskStatus,
    BackgroundTaskType,
)
from videocenter.models.download import DownloadTask
from videocenter.models.hls import HlsTask, HlsTaskStatus
from videocenter.models.scan import ScanTask, ScanTaskStatus
from videocenter.schemas.background_task import (
    BackgroundTaskCleanupRequest,
    BackgroundTaskCleanupResponse,
    BackgroundTaskLogPage,
    BackgroundTaskPage,
    BackgroundTaskRead,
)
from videocenter.services.analysis_tasks import retry_analysis_task, start_analysis_task
from videocenter.services.background_tasks import (
    record_background_task_log,
    sync_hls_background_task,
    sync_scan_background_task,
)
from videocenter.services.downloads import cancel_download, retry_download
from videocenter.services.hls import start_hls_task
from videocenter.services.local_library import start_scan_task
from videocenter.services.task_events import task_event_broker

router = APIRouter()


@router.websocket("/ws")
async def task_status_websocket(websocket: WebSocket):
    task_type_value = websocket.query_params.get("task_type")
    status_value = websocket.query_params.get("status")
    try:
        task_type = BackgroundTaskType(task_type_value) if task_type_value is not None else None
        task_status = BackgroundTaskStatus(status_value) if status_value is not None else None
    except ValueError:
        await websocket.accept()
        await websocket.send_json(
            {
                "type": "error",
                "code": "INVALID_TASK_EVENT_FILTER",
                "message": "任务类型或状态筛选值无效",
            }
        )
        await websocket.close(code=1008)
        return

    await websocket.accept()
    await websocket.send_json(
        {
            "type": "connected",
            "task_type": task_type.value if task_type else None,
            "status": task_status.value if task_status else None,
        }
    )
    async with task_event_broker.subscribe(
        task_type=task_type,
        status=task_status,
    ) as event_queue:
        try:
            while True:
                event_waiter = asyncio.create_task(event_queue.get())
                client_waiter = asyncio.create_task(websocket.receive_text())
                done, pending = await asyncio.wait(
                    {event_waiter, client_waiter},
                    timeout=25,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for waiter in pending:
                    waiter.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
                if not done:
                    await websocket.send_json(
                        {
                            "type": "heartbeat",
                            "sent_at": datetime.now().isoformat(),
                        }
                    )
                    continue
                if event_waiter in done:
                    await websocket.send_json(event_waiter.result())
                if client_waiter in done:
                    message = client_waiter.result()
                    if message.casefold() == "ping":
                        await websocket.send_json(
                            {
                                "type": "pong",
                                "sent_at": datetime.now().isoformat(),
                            }
                        )
        except WebSocketDisconnect:
            return


@router.get("", response_model=BackgroundTaskPage)
def list_background_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    task_type: BackgroundTaskType | None = Query(default=None),
    task_status: BackgroundTaskStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
):
    filters = []
    if task_type is not None:
        filters.append(BackgroundTask.task_type == task_type)
    if task_status is not None:
        filters.append(BackgroundTask.status == task_status)
    total = db.scalar(select(func.count(BackgroundTask.id)).where(*filters)) or 0
    total_pages = (total + page_size - 1) // page_size
    items = db.scalars(
        select(BackgroundTask)
        .where(*filters)
        .order_by(BackgroundTask.created_at.desc(), BackgroundTask.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return BackgroundTaskPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1 and total_pages > 0,
    )


@router.post("/cleanup", response_model=BackgroundTaskCleanupResponse)
def cleanup_background_tasks(
    payload: BackgroundTaskCleanupRequest,
    db: Session = Depends(get_db),
):
    cutoff = datetime.now() - timedelta(days=payload.max_age_days)
    task_ids = list(
        db.scalars(
            select(BackgroundTask.id).where(
                BackgroundTask.status.in_(
                    [
                        BackgroundTaskStatus.COMPLETED,
                        BackgroundTaskStatus.FAILED,
                        BackgroundTaskStatus.CANCELLED,
                    ]
                ),
                BackgroundTask.completed_at.is_not(None),
                BackgroundTask.completed_at <= cutoff,
            )
        ).all()
    )
    if not task_ids:
        return BackgroundTaskCleanupResponse(
            deleted_task_count=0,
            deleted_task_ids=[],
            deleted_log_count=0,
        )
    deleted_log_count = (
        db.scalar(
            select(func.count(BackgroundTaskLog.id)).where(BackgroundTaskLog.task_id.in_(task_ids))
        )
        or 0
    )
    db.execute(delete(BackgroundTaskLog).where(BackgroundTaskLog.task_id.in_(task_ids)))
    db.execute(delete(BackgroundTask).where(BackgroundTask.id.in_(task_ids)))
    db.commit()
    return BackgroundTaskCleanupResponse(
        deleted_task_count=len(task_ids),
        deleted_task_ids=task_ids,
        deleted_log_count=deleted_log_count,
    )


@router.get("/{task_id}", response_model=BackgroundTaskRead)
def get_background_task(
    task_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    task = db.get(BackgroundTask, task_id)
    if task is None:
        raise NotFoundError("后台任务不存在", code="BACKGROUND_TASK_NOT_FOUND")
    return task


@router.get("/{task_id}/logs", response_model=BackgroundTaskLogPage)
def list_background_task_logs(
    task_id: Annotated[int, Path(gt=0)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    event: str | None = Query(default=None, min_length=1, max_length=100),
    db: Session = Depends(get_db),
):
    if db.get(BackgroundTask, task_id) is None:
        raise NotFoundError("后台任务不存在", code="BACKGROUND_TASK_NOT_FOUND")
    filters = [BackgroundTaskLog.task_id == task_id]
    if event is not None:
        filters.append(BackgroundTaskLog.event == event)
    total = db.scalar(select(func.count(BackgroundTaskLog.id)).where(*filters)) or 0
    total_pages = (total + page_size - 1) // page_size
    items = db.scalars(
        select(BackgroundTaskLog)
        .where(*filters)
        .order_by(BackgroundTaskLog.created_at.desc(), BackgroundTaskLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return BackgroundTaskLogPage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1 and total_pages > 0,
    )


@router.post("/{task_id}/cancel", response_model=BackgroundTaskRead)
def cancel_background_task(
    task_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    task = db.get(BackgroundTask, task_id)
    if task is None:
        raise NotFoundError("后台任务不存在", code="BACKGROUND_TASK_NOT_FOUND")
    if task.status == BackgroundTaskStatus.CANCELLED:
        return task
    if not task.cancellable or task.status not in {
        BackgroundTaskStatus.WAITING,
        BackgroundTaskStatus.RUNNING,
        BackgroundTaskStatus.PAUSED,
    }:
        raise ConflictError(
            "当前后台任务不能取消",
            code="BACKGROUND_TASK_NOT_CANCELLABLE",
            details={
                "task_type": task.task_type.value,
                "status": task.status.value,
            },
        )
    if task.task_type != BackgroundTaskType.DOWNLOAD or task.source_task_id is None:
        raise ConflictError(
            "该类型后台任务尚未接入取消执行器",
            code="BACKGROUND_TASK_CANCEL_NOT_SUPPORTED",
            details={"task_type": task.task_type.value},
        )
    download = db.get(DownloadTask, task.source_task_id)
    if download is None:
        raise ConflictError(
            "后台任务关联的下载任务不存在",
            code="BACKGROUND_TASK_SOURCE_MISSING",
        )
    cancel_download(db, download)
    db.refresh(task)
    return task


@router.post("/{task_id}/retry", response_model=BackgroundTaskRead)
def retry_background_task(
    task_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    task = db.get(BackgroundTask, task_id)
    if task is None:
        raise NotFoundError("后台任务不存在", code="BACKGROUND_TASK_NOT_FOUND")
    if task.status != BackgroundTaskStatus.FAILED:
        raise ConflictError(
            "只有失败状态的后台任务可以重试",
            code="BACKGROUND_TASK_NOT_RETRYABLE",
            details={"status": task.status.value},
        )
    if task.source_task_id is None:
        raise ConflictError(
            "后台任务缺少来源任务，无法重试",
            code="BACKGROUND_TASK_SOURCE_MISSING",
        )

    if task.task_type == BackgroundTaskType.DOWNLOAD:
        source = db.get(DownloadTask, task.source_task_id)
        if source is None:
            raise ConflictError(
                "后台任务关联的下载任务不存在",
                code="BACKGROUND_TASK_SOURCE_MISSING",
            )
        retry_download(db, source)
        db.refresh(task)
        record_background_task_log(
            db,
            task,
            event="retry",
            message="下载任务已重新排队",
            details={"attempt": task.attempt},
        )
        db.commit()
        db.refresh(task)
        return task

    if task.task_type == BackgroundTaskType.MEDIA_ANALYSIS:
        source = db.get(AnalysisTask, task.source_task_id)
        if source is None:
            raise ConflictError(
                "后台任务关联的分析任务不存在",
                code="BACKGROUND_TASK_SOURCE_MISSING",
            )
        retry_source = retry_analysis_task(db, source)
        start_analysis_task(retry_source.id)
        retried = db.scalar(
            select(BackgroundTask).where(
                BackgroundTask.task_type == BackgroundTaskType.MEDIA_ANALYSIS,
                BackgroundTask.source_task_id == retry_source.id,
            )
        )
        record_background_task_log(
            db,
            retried,
            event="retry",
            message="媒体分析任务已创建重试任务",
            details={"retried_from_task_id": task.id},
        )
        db.commit()
        db.refresh(retried)
        return retried

    if task.task_type == BackgroundTaskType.MEDIA_SCAN:
        source = db.get(ScanTask, task.source_task_id)
        if source is None:
            raise ConflictError(
                "后台任务关联的扫描任务不存在",
                code="BACKGROUND_TASK_SOURCE_MISSING",
            )
        source.status = ScanTaskStatus.WAITING
        source.progress = 0
        source.processed_files = 0
        source.error_message = None
        source.started_at = None
        source.completed_at = None
        task.max_attempts = max(task.max_attempts, task.attempt + 1)
        task.attempt += 1
        sync_scan_background_task(db, source)
        record_background_task_log(
            db,
            task,
            event="retry",
            message="本地扫描任务已重新排队",
            details={"attempt": task.attempt},
        )
        db.commit()
        start_scan_task(source.id)
        db.refresh(task)
        return task

    if task.task_type == BackgroundTaskType.HLS_TRANSCODE:
        source = db.get(HlsTask, task.source_task_id)
        if source is None:
            raise ConflictError(
                "后台任务关联的 HLS 任务不存在",
                code="BACKGROUND_TASK_SOURCE_MISSING",
            )
        source.status = HlsTaskStatus.WAITING
        source.progress = 0
        source.error_message = None
        source.started_at = None
        source.completed_at = None
        task.max_attempts = max(task.max_attempts, task.attempt + 1)
        task.attempt += 1
        sync_hls_background_task(db, source)
        record_background_task_log(
            db,
            task,
            event="retry",
            message="HLS 转码任务已重新排队",
            details={"attempt": task.attempt},
        )
        db.commit()
        start_hls_task(source.id)
        db.refresh(task)
        return task

    raise ConflictError(
        "该类型后台任务尚未接入失败重试",
        code="BACKGROUND_TASK_RETRY_NOT_SUPPORTED",
        details={"task_type": task.task_type.value},
    )
