from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from videocenter.core.database import get_db
from videocenter.models.media import LocalResource
from videocenter.services.streaming import iter_file_range, parse_range_header

router = APIRouter()


@router.get("/{resource_id}")
def stream_video(
    resource_id: int,
    range_header: str | None = Header(default=None, alias="Range"),
    db: Session = Depends(get_db),
):
    resource = db.get(LocalResource, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="本地资源不存在")
    path = Path(resource.file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="视频文件已丢失")

    file_size = path.stat().st_size
    try:
        byte_range = parse_range_header(range_header, file_size)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=416,
            detail="无效的 Range 请求",
            headers={"Content-Range": f"bytes */{file_size}"},
        ) from None

    if byte_range is None:
        return FileResponse(
            path, media_type=resource.mime_type, headers={"Accept-Ranges": "bytes"}
        )

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
