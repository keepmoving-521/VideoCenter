from datetime import datetime
from email.utils import formatdate
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from fastapi import Path as ApiPath
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from videocenter.core.database import get_db
from videocenter.core.exceptions import AppException, NotFoundError
from videocenter.models.media import LocalResource
from videocenter.schemas.streaming import PlaybackResourceDetail
from videocenter.services.downloads import update_media_download_status
from videocenter.services.streaming import (
    ByteRange,
    is_not_modified,
    iter_file_range,
    parse_range_header,
)

router = APIRouter()
CACHE_CONTROL = "private, max-age=3600, no-transform"


@router.get("/{resource_id}")
def stream_video(
    resource_id: Annotated[int, ApiPath(gt=0)],
    range_header: Annotated[
        str | None,
        Header(alias="Range", max_length=512),
    ] = None,
    if_none_match: Annotated[
        str | None,
        Header(alias="If-None-Match", max_length=512),
    ] = None,
    if_modified_since: Annotated[
        str | None,
        Header(alias="If-Modified-Since", max_length=128),
    ] = None,
    db: Session = Depends(get_db),
):
    resource, path, file_size, byte_range, headers, not_modified = _prepare_video_response(
        db,
        resource_id=resource_id,
        range_header=range_header,
        if_none_match=if_none_match,
        if_modified_since=if_modified_since,
    )
    if not_modified:
        return Response(status_code=304, headers=headers)

    if byte_range is None:
        return FileResponse(path, media_type=resource.mime_type, headers=headers)

    return StreamingResponse(
        iter_file_range(str(path), byte_range),
        status_code=206,
        media_type=resource.mime_type,
        headers={
            **headers,
            "Content-Range": f"bytes {byte_range.start}-{byte_range.end}/{file_size}",
            "Content-Length": str(byte_range.length),
        },
    )


@router.head("/{resource_id}")
def head_video(
    resource_id: Annotated[int, ApiPath(gt=0)],
    range_header: Annotated[
        str | None,
        Header(alias="Range", max_length=512),
    ] = None,
    if_none_match: Annotated[
        str | None,
        Header(alias="If-None-Match", max_length=512),
    ] = None,
    if_modified_since: Annotated[
        str | None,
        Header(alias="If-Modified-Since", max_length=128),
    ] = None,
    db: Session = Depends(get_db),
):
    resource, _, file_size, byte_range, headers, not_modified = _prepare_video_response(
        db,
        resource_id=resource_id,
        range_header=range_header,
        if_none_match=if_none_match,
        if_modified_since=if_modified_since,
    )
    if not_modified:
        return Response(status_code=304, headers=headers)
    if byte_range is None:
        headers["Content-Length"] = str(file_size)
        return Response(status_code=200, media_type=resource.mime_type, headers=headers)
    headers.update(
        {
            "Content-Range": f"bytes {byte_range.start}-{byte_range.end}/{file_size}",
            "Content-Length": str(byte_range.length),
        }
    )
    return Response(status_code=206, media_type=resource.mime_type, headers=headers)


@router.get("/{resource_id}/details", response_model=PlaybackResourceDetail)
def get_playback_resource_detail(
    resource_id: Annotated[int, ApiPath(gt=0)],
    db: Session = Depends(get_db),
):
    resource = db.get(LocalResource, resource_id)
    if resource is None:
        raise NotFoundError("本地资源不存在", code="LOCAL_RESOURCE_NOT_FOUND")
    file_exists = Path(resource.file_path).is_file()
    if not file_exists:
        _mark_resource_missing(db, resource)
    base_url = f"/api/v1/stream/{resource.id}"
    return PlaybackResourceDetail(
        resource=resource,
        playable=file_exists and resource.is_available,
        file_exists=file_exists,
        stream_url=base_url,
        head_url=base_url,
        cover_url=(
            f"/api/v1/local-resources/{resource.id}/cover" if resource.cover_image_path else None
        ),
        preview_urls=[
            f"/api/v1/local-resources/{resource.id}/previews/{index}"
            for index in range(len(resource.preview_thumbnail_paths))
        ],
        supports_range=True,
        cache_control=CACHE_CONTROL,
    )


def _prepare_video_response(
    db: Session,
    *,
    resource_id: int,
    range_header: str | None,
    if_none_match: str | None,
    if_modified_since: str | None,
) -> tuple[LocalResource, Path, int, ByteRange | None, dict[str, str], bool]:
    resource = db.get(LocalResource, resource_id)
    if not resource:
        raise NotFoundError("本地资源不存在", code="LOCAL_RESOURCE_NOT_FOUND")
    path = Path(resource.file_path)
    if not path.is_file():
        _mark_resource_missing(db, resource)
        raise NotFoundError("视频文件已丢失", code="VIDEO_FILE_MISSING")

    stat = path.stat()
    file_size = stat.st_size
    try:
        byte_range = parse_range_header(range_header, file_size)
    except (ValueError, TypeError):
        raise AppException(
            "无效的 Range 请求",
            status_code=416,
            code="INVALID_BYTE_RANGE",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes */{file_size}",
            },
        ) from None
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": CACHE_CONTROL,
        "ETag": f'"{stat.st_mtime_ns:x}-{file_size:x}"',
        "Last-Modified": formatdate(stat.st_mtime, usegmt=True),
    }
    not_modified = range_header is None and is_not_modified(
        etag=headers["ETag"],
        modified_at=stat.st_mtime,
        if_none_match=if_none_match,
        if_modified_since=if_modified_since,
    )
    return resource, path, file_size, byte_range, headers, not_modified


def _mark_resource_missing(db: Session, resource: LocalResource) -> None:
    if resource.is_available or resource.missing_at is None:
        resource.is_available = False
        resource.missing_at = datetime.now()
        db.flush()
        update_media_download_status(db, resource.media_id)
        db.commit()
