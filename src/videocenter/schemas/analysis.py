from datetime import datetime

from pydantic import BaseModel, ConfigDict

from videocenter.models.analysis import AnalysisTaskStatus


class AnalysisFailureRead(BaseModel):
    resource_id: int
    error: str


class AnalysisTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    retry_of_task_id: int | None
    resource_ids: list[int]
    force: bool
    status: AnalysisTaskStatus
    progress: float
    total_resources: int
    processed_resources: int
    analyzed_resource_ids: list[int]
    skipped_resource_ids: list[int]
    missing_resource_ids: list[int]
    failures: list[AnalysisFailureRead]
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
