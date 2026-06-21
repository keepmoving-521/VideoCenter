from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.core.database import get_db
from videocenter.core.exceptions import BadRequestError, NotFoundError
from videocenter.models.media import LocalResource, Media
from videocenter.models.scan import ScanTask
from videocenter.schemas.media import (
    DuplicateLocalResourceGroup,
    DuplicateLocalResourcesResponse,
    LocalResourceAssociationRequest,
    LocalResourceBatchAssociationRequest,
    LocalResourceBatchAssociationResponse,
    LocalResourceRead,
    LocalScanRequest,
)
from videocenter.schemas.scan import ScanTaskRead
from videocenter.services.local_file_hashes import find_duplicate_local_resources
from videocenter.services.local_library import (
    create_scan_task,
    resolve_library_path,
    start_scan_task,
)
from videocenter.services.local_resource_associations import associate_local_resources

router = APIRouter()


@router.get("", response_model=list[LocalResourceRead])
def list_resources(db: Session = Depends(get_db)):
    return db.scalars(select(LocalResource).order_by(LocalResource.id.desc())).all()


@router.get(
    "/duplicates",
    response_model=DuplicateLocalResourcesResponse,
)
def list_duplicate_resources(db: Session = Depends(get_db)):
    groups = find_duplicate_local_resources(db)
    response_groups = [
        DuplicateLocalResourceGroup(
            checksum_sha256=group[0].checksum_sha256,
            file_size=group[0].file_size,
            duplicate_count=len(group),
            resources=group,
        )
        for group in groups
    ]
    return DuplicateLocalResourcesResponse(
        group_count=len(response_groups),
        duplicate_file_count=sum(group.duplicate_count for group in response_groups),
        reclaimable_bytes=sum(
            group.file_size * (group.duplicate_count - 1) for group in response_groups
        ),
        groups=response_groups,
    )


@router.post(
    "/batch-associate",
    response_model=LocalResourceBatchAssociationResponse,
)
def batch_associate_resources(
    payload: LocalResourceBatchAssociationRequest,
    db: Session = Depends(get_db),
):
    resources, missing_ids = associate_local_resources(
        db,
        resource_ids=payload.resource_ids,
        media_id=payload.media_id,
    )
    return LocalResourceBatchAssociationResponse(
        media_id=payload.media_id,
        associated_count=len(resources),
        associated_resource_ids=[resource.id for resource in resources],
        missing_resource_ids=missing_ids,
    )


@router.post(
    "/scan",
    response_model=ScanTaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def scan_resources(payload: LocalScanRequest, db: Session = Depends(get_db)):
    if payload.media_id is not None and not db.get(Media, payload.media_id):
        raise NotFoundError("影视条目不存在", code="MEDIA_NOT_FOUND")
    try:
        path = resolve_library_path(payload.path)
    except ValueError as exc:
        raise BadRequestError(str(exc), code="INVALID_SCAN_PATH") from exc
    task = create_scan_task(
        db,
        path=path,
        media_id=payload.media_id,
        incremental=payload.incremental,
    )
    start_scan_task(task.id)
    return task


@router.put(
    "/{resource_id}/association",
    response_model=LocalResourceRead,
)
def associate_resource(
    resource_id: Annotated[int, Path(gt=0)],
    payload: LocalResourceAssociationRequest,
    db: Session = Depends(get_db),
):
    resources, missing_ids = associate_local_resources(
        db,
        resource_ids=[resource_id],
        media_id=payload.media_id,
    )
    if missing_ids:
        raise NotFoundError("本地资源不存在", code="LOCAL_RESOURCE_NOT_FOUND")
    return resources[0]


@router.get("/scan-tasks", response_model=list[ScanTaskRead])
def list_scan_tasks(db: Session = Depends(get_db)):
    return db.scalars(select(ScanTask).order_by(ScanTask.id.desc())).all()


@router.get("/scan-tasks/{task_id}", response_model=ScanTaskRead)
def get_scan_task(
    task_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    task = db.get(ScanTask, task_id)
    if task is None:
        raise NotFoundError("扫描任务不存在", code="SCAN_TASK_NOT_FOUND")
    return task
