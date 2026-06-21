from datetime import datetime

from pydantic import BaseModel, ConfigDict

from videocenter.models.background_task import BackgroundTaskStatus, BackgroundTaskType


class BackgroundTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_type: BackgroundTaskType
    status: BackgroundTaskStatus
    title: str
    source_task_id: int | None
    parent_task_id: int | None
    priority: int
    progress: float
    processed_items: int
    total_items: int | None
    attempt: int
    max_attempts: int
    cancellable: bool
    pause_supported: bool
    cancel_requested: bool
    worker_id: str | None
    task_payload: dict
    task_result: dict | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    heartbeat_at: datetime | None
