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
from videocenter.services.streaming import ByteRange, iter_file_range, parse_range_header

router = APIRouter()


@router.get("/{resource_id}")
def stream_video(
    resource_id: Annotated[int, ApiPath(gt=0)],
    range_header: Annotated[
        str | None,
        Header(alias="Range", max_length=512),
    ] = None,
    db: Session = Depends(get_db),
):
    resource, path, file_size, byte_range, headers = _prepare_video_response(
        db,
        resource_id=resource_id,
        range_header=range_header,
    )

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
    db: Session = Depends(get_db),
):
    resource, _, file_size, byte_range, headers = _prepare_video_response(
        db,
        resource_id=resource_id,
        range_header=range_header,
    )
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


def _prepare_video_response(
    db: Session,
    *,
    resource_id: int,
    range_header: str | None,
) -> tuple[LocalResource, Path, int, ByteRange | None, dict[str, str]]:
    resource = db.get(LocalResource, resource_id)
    if not resource:
        raise NotFoundError("本地资源不存在", code="LOCAL_RESOURCE_NOT_FOUND")
    path = Path(resource.file_path)
    if not path.is_file():
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
        "ETag": f'"{stat.st_mtime_ns:x}-{file_size:x}"',
        "Last-Modified": formatdate(stat.st_mtime, usegmt=True),
    }
    return resource, path, file_size, byte_range, headers
