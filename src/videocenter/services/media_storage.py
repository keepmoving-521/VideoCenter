import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.models.media import LocalResource
from videocenter.models.media_directory import MediaDirectory
from videocenter.schemas.media_directory import MediaDirectoryStorageRead


def get_media_directory_storage(
    db: Session,
    directory: MediaDirectory,
) -> MediaDirectoryStorageRead:
    directory_path = Path(directory.path).resolve()
    usage = shutil.disk_usage(directory_path)
    resources = db.scalars(select(LocalResource).where(LocalResource.is_available.is_(True))).all()
    managed_resources = [
        resource for resource in resources if _is_inside(Path(resource.file_path), directory_path)
    ]
    usage_percent = round(usage.used / usage.total * 100, 2) if usage.total else 0.0
    return MediaDirectoryStorageRead(
        directory_id=directory.id,
        name=directory.name,
        path=directory.path,
        total_bytes=usage.total,
        used_bytes=usage.used,
        free_bytes=usage.free,
        usage_percent=usage_percent,
        managed_file_count=len(managed_resources),
        managed_file_bytes=sum(resource.file_size for resource in managed_resources),
        warning_enabled=directory.capacity_warning_enabled,
        warning_threshold_percent=directory.capacity_warning_threshold_percent,
        warning_triggered=(
            directory.capacity_warning_enabled
            and usage_percent >= directory.capacity_warning_threshold_percent
        ),
    )


def _is_inside(resource_path: Path, directory_path: Path) -> bool:
    try:
        return resource_path.resolve().is_relative_to(directory_path)
    except (OSError, RuntimeError, ValueError):
        return False
