from datetime import datetime

from pydantic import BaseModel, ConfigDict

from videocenter.models.scan import ScanTaskStatus


class ScanTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    path: str
    media_id: int | None
    incremental: bool
    status: ScanTaskStatus
    progress: float
    total_files: int
    processed_files: int
    discovered_files: int
    added_files: int
    updated_files: int
    skipped_files: int
    missing_files: int
    restored_files: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
