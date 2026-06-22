from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from videocenter.core.database import get_db
from videocenter.core.exceptions import ConflictError, NotFoundError
from videocenter.models.background_task import (
    BackgroundTask,
    BackgroundTaskStatus,
    BackgroundTaskType,
)
from videocenter.models.download import DownloadTask
from videocenter.schemas.background_task import BackgroundTaskPage, BackgroundTaskRead
from videocenter.services.downloads import cancel_download

router = APIRouter()


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


@router.get("/{task_id}", response_model=BackgroundTaskRead)
def get_background_task(
    task_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    task = db.get(BackgroundTask, task_id)
    if task is None:
        raise NotFoundError("后台任务不存在", code="BACKGROUND_TASK_NOT_FOUND")
    return task


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
