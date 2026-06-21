from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from videocenter.core.database import Base


class AnalysisTaskStatus(StrEnum):
    WAITING = "waiting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    retry_of_task_id: Mapped[int | None] = mapped_column(
        ForeignKey("analysis_tasks.id", ondelete="SET NULL"),
        index=True,
    )
    resource_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    force: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    status: Mapped[AnalysisTaskStatus] = mapped_column(
        Enum(AnalysisTaskStatus),
        default=AnalysisTaskStatus.WAITING,
        index=True,
    )
    progress: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    total_resources: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    processed_resources: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    analyzed_resource_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    skipped_resource_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    missing_resource_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    failures: Mapped[list[dict]] = mapped_column(JSON, default=list)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
