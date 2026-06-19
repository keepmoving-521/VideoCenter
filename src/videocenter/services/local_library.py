import mimetypes
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.core.config import get_settings
from videocenter.models.media import LocalResource
from videocenter.schemas.media import LocalScanResult

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".ts"}


def resolve_library_path(requested_path: str | None) -> Path:
    root = get_settings().media_root
    candidate = Path(requested_path).expanduser().resolve() if requested_path else root
    if not candidate.is_relative_to(root):
        raise ValueError("扫描目录必须位于媒体根目录内")
    if not candidate.is_dir():
        raise ValueError("扫描目录不存在")
    return candidate


def scan_local_library(
    db: Session, requested_path: str | None = None, media_id: int | None = None
) -> LocalScanResult:
    directory = resolve_library_path(requested_path)
    files = [
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    ]
    added = 0
    updated = 0

    for path in files:
        normalized = str(path.resolve())
        resource = db.scalar(
            select(LocalResource).where(LocalResource.file_path == normalized)
        )
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if resource:
            resource.file_size = path.stat().st_size
            resource.mime_type = mime_type
            if media_id is not None:
                resource.media_id = media_id
            updated += 1
        else:
            db.add(
                LocalResource(
                    media_id=media_id,
                    file_path=normalized,
                    file_name=path.name,
                    file_size=path.stat().st_size,
                    mime_type=mime_type,
                )
            )
            added += 1

    db.commit()
    return LocalScanResult(scanned=len(files), added=added, updated=updated)
