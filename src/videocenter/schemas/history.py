from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class HistoryUpsert(BaseModel):
    media_id: int
    resource_id: int | None = None
    position_seconds: float = Field(ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)


class HistoryRead(HistoryUpsert):
    model_config = ConfigDict(from_attributes=True)

    id: int
    watched_at: datetime
