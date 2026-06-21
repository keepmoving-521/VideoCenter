from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi import Path as ApiPath
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.core.config import get_settings
from videocenter.core.database import get_db
from videocenter.core.exceptions import BadRequestError, NotFoundError
from videocenter.models.media import LocalResource, Media
from videocenter.models.scan import ScanTask
from videocenter.schemas.media import (
    DuplicateLocalResourceGroup,
    DuplicateLocalResourcesResponse,
    InvalidLocalResourceCleanupResponse,
    LocalResourceAssociationRequest,
    LocalResourceBatchAnalysisRequest,
    LocalResourceBatchAnalysisResponse,
    LocalResourceBatchAssociationRequest,
    LocalResourceBatchAssociationResponse,
    LocalResourceRead,
    LocalResourceRenameRequest,
    LocalScanRequest,
)
from videocenter.schemas.scan import ScanTaskRead
from videocenter.services.local_file_hashes import find_duplicate_local_resources
from videocenter.services.local_file_operations import (
    cleanup_invalid_local_resources,
    rename_local_resource,
    safely_delete_local_resource,
)
from videocenter.services.local_library import (
    create_scan_task,
    resolve_library_path,
    start_scan_task,
)
from videocenter.services.local_resource_analysis import analyze_local_resource
from videocenter.services.local_resource_associations import associate_local_resources
from videocenter.services.media_artwork import MEDIA_CACHE_DIRECTORY_NAME

router = APIRouter()


@router.get("", response_model=list[LocalResourceRead])
def list_resources(db: Session = Depends(get_db)):
    return db.scalars(select(LocalResource).order_by(LocalResource.id.desc())).all()


@router.get("/{resource_id}/cover")
def get_resource_cover(
    resource_id: Annotated[int, ApiPath(gt=0)],
    db: Session = Depends(get_db),
):
    resource = _get_resource_or_404(db, resource_id)
    return _artwork_response(resource.cover_image_path)


@router.get("/{resource_id}/previews/{preview_index}")
def get_resource_preview(
    resource_id: Annotated[int, ApiPath(gt=0)],
    preview_index: Annotated[int, ApiPath(ge=0)],
    db: Session = Depends(get_db),
):
    resource = _get_resource_or_404(db, resource_id)
    if preview_index >= len(resource.preview_thumbnail_paths):
        raise NotFoundError("预览缩略图不存在", code="PREVIEW_THUMBNAIL_NOT_FOUND")
    return _artwork_response(resource.preview_thumbnail_paths[preview_index])


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
    "/cleanup-invalid",
    response_model=InvalidLocalResourceCleanupResponse,
)
def cleanup_invalid_resources(db: Session = Depends(get_db)):
    deleted_ids = cleanup_invalid_local_resources(db)
    return InvalidLocalResourceCleanupResponse(
        deleted_count=len(deleted_ids),
        deleted_resource_ids=deleted_ids,
    )


@router.post(
    "/batch-analyze",
    response_model=LocalResourceBatchAnalysisResponse,
)
def batch_analyze_resources(
    payload: LocalResourceBatchAnalysisRequest,
    db: Session = Depends(get_db),
):
    resources = {
        resource.id: resource
        for resource in db.scalars(
            select(LocalResource).where(LocalResource.id.in_(payload.resource_ids))
        ).all()
    }
    analyzed_ids: list[int] = []
    skipped_ids: list[int] = []
    missing_ids: list[int] = []
    failures: list[dict[str, object]] = []
    for resource_id in payload.resource_ids:
        resource = resources.get(resource_id)
        if resource is None:
            missing_ids.append(resource_id)
            continue
        try:
            with db.begin_nested():
                result = analyze_local_resource(resource, force=payload.force)
        except Exception as exc:
            failures.append({"resource_id": resource_id, "error": str(exc)})
            continue
        if result == "analyzed":
            analyzed_ids.append(resource_id)
        elif result == "skipped":
            skipped_ids.append(resource_id)
        else:
            missing_ids.append(resource_id)
    db.commit()
    return LocalResourceBatchAnalysisResponse(
        requested_count=len(payload.resource_ids),
        analyzed_count=len(analyzed_ids),
        analyzed_resource_ids=analyzed_ids,
        skipped_resource_ids=skipped_ids,
        missing_resource_ids=missing_ids,
        failures=failures,
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
    resource_id: Annotated[int, ApiPath(gt=0)],
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


@router.put(
    "/{resource_id}/rename",
    response_model=LocalResourceRead,
)
def rename_resource(
    resource_id: Annotated[int, ApiPath(gt=0)],
    payload: LocalResourceRenameRequest,
    db: Session = Depends(get_db),
):
    return rename_local_resource(
        db,
        resource_id=resource_id,
        new_file_name=payload.file_name,
    )


@router.delete(
    "/{resource_id}/file",
    response_model=LocalResourceRead,
)
def safely_delete_resource_file(
    resource_id: Annotated[int, ApiPath(gt=0)],
    db: Session = Depends(get_db),
):
    return safely_delete_local_resource(db, resource_id=resource_id)


@router.get("/scan-tasks", response_model=list[ScanTaskRead])
def list_scan_tasks(db: Session = Depends(get_db)):
    return db.scalars(select(ScanTask).order_by(ScanTask.id.desc())).all()


@router.get("/scan-tasks/{task_id}", response_model=ScanTaskRead)
def get_scan_task(
    task_id: Annotated[int, ApiPath(gt=0)],
    db: Session = Depends(get_db),
):
    task = db.get(ScanTask, task_id)
    if task is None:
        raise NotFoundError("扫描任务不存在", code="SCAN_TASK_NOT_FOUND")
    return task


def _get_resource_or_404(db: Session, resource_id: int) -> LocalResource:
    resource = db.get(LocalResource, resource_id)
    if resource is None:
        raise NotFoundError("本地资源不存在", code="LOCAL_RESOURCE_NOT_FOUND")
    return resource


def _artwork_response(file_path: str | None) -> FileResponse:
    if file_path is None:
        raise NotFoundError("视频视觉资源不存在", code="VIDEO_ARTWORK_NOT_FOUND")
    path = Path(file_path).resolve()
    cache_root = (get_settings().media_root / MEDIA_CACHE_DIRECTORY_NAME).resolve()
    if not path.is_relative_to(cache_root):
        raise NotFoundError("视频视觉资源路径无效", code="INVALID_VIDEO_ARTWORK_PATH")
    if not path.is_file():
        raise NotFoundError("视频视觉资源文件已丢失", code="VIDEO_ARTWORK_FILE_MISSING")
    return FileResponse(path, media_type="image/jpeg")
