from datetime import datetime

from pydantic import BaseModel, ConfigDict

from videocenter.models.hls import HlsTaskStatus


class HlsTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resource_id: int
    status: HlsTaskStatus
    progress: float
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
            playlist_url=(
                f"/api/v1/stream/hls/{task.id}/index.m3u8"
                if task.status == HlsTaskStatus.COMPLETED
                else None
            ),
            error_message=task.error_message,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
        )
