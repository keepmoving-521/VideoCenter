from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from fastapi import Path as ApiPath
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from videocenter.core.database import get_db
from videocenter.core.exceptions import AppException, NotFoundError
from videocenter.models.media import LocalResource
from videocenter.services.streaming import iter_file_range, parse_range_header

router = APIRouter()


@router.get("/{resource_id}")
def stream_video(
    resource_id: Annotated[int, ApiPath(gt=0)],
    range_header: Annotated[
        str | None,
        Header(alias="Range", max_length=128, pattern=r"^bytes=[0-9]*-[0-9]*$"),
    ] = None,
    db: Session = Depends(get_db),
):
    resource = db.get(LocalResource, resource_id)
    if not resource:
        raise NotFoundError("本地资源不存在", code="LOCAL_RESOURCE_NOT_FOUND")
    path = Path(resource.file_path)
    if not path.is_file():
        raise NotFoundError("视频文件已丢失", code="VIDEO_FILE_MISSING")

    file_size = path.stat().st_size
    try:
        byte_range = parse_range_header(range_header, file_size)
    except (ValueError, TypeError):
        raise AppException(
            "无效的 Range 请求",
            status_code=416,
            code="INVALID_BYTE_RANGE",
            headers={"Content-Range": f"bytes */{file_size}"},
        ) from None

    if byte_range is None:
        return FileResponse(path, media_type=resource.mime_type, headers={"Accept-Ranges": "bytes"})

    return StreamingResponse(
        iter_file_range(str(path), byte_range),
        status_code=206,
        media_type=resource.mime_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {byte_range.start}-{byte_range.end}/{file_size}",
            "Content-Length": str(byte_range.length),
        },
    )
