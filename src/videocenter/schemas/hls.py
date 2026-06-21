from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from videocenter.models.hls import HlsTaskStatus
from videocenter.schemas.common import ApiRequestModel


class HlsTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resource_id: int
    status: HlsTaskStatus
    progress: float
    cache_available: bool
    playlist_url: str | None = None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    @classmethod
    def from_task(cls, task) -> "HlsTaskRead":
        return cls(
            id=task.id,
            resource_id=task.resource_id,
            status=task.status,
            progress=task.progress,
            cache_available=bool(
                task.playlist_path
                and task.status == HlsTaskStatus.COMPLETED
                and Path(task.playlist_path).is_file()
            ),
            playlist_url=(
                f"/api/v1/stream/hls/{task.id}/index.m3u8"
                if task.playlist_path
                and task.status == HlsTaskStatus.COMPLETED
                and Path(task.playlist_path).is_file()
                else None
            ),
            error_message=task.error_message,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
        )


class HlsCacheCleanupRequest(ApiRequestModel):
    max_age_hours: int | None = Field(default=None, ge=0, le=87600)


class HlsCacheCleanupResult(BaseModel):
    cleaned_task_count: int
    cleaned_task_ids: list[int]
    removed_directory_count: int
    reclaimed_bytes: int
