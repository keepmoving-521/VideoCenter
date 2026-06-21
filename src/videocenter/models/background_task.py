from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from videocenter.core.database import Base


class BackgroundTaskType(StrEnum):
    DOWNLOAD = "download"
    MEDIA_SCAN = "media_scan"
    MEDIA_ANALYSIS = "media_analysis"
    HLS_TRANSCODE = "hls_transcode"
    GENERIC = "generic"


class BackgroundTaskStatus(StrEnum):
    WAITING = "waiting"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BackgroundTask(Base):
    __tablename__ = "background_tasks"
    __table_args__ = (
        UniqueConstraint(
            "task_type",
            "source_task_id",
            name="uq_background_task_type_source",
        ),
        CheckConstraint(
            "priority >= -100 AND priority <= 100",
            name="ck_background_task_priority_range",
        ),
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="ck_background_task_progress_range",
        ),
        CheckConstraint(
            "processed_items >= 0",
            name="ck_background_task_processed_non_negative",
        ),
        CheckConstraint(
            "total_items IS NULL OR total_items >= 0",
            name="ck_background_task_total_non_negative",
        ),
        CheckConstraint(
            "total_items IS NULL OR processed_items <= total_items",
            name="ck_background_task_processed_not_above_total",
        ),
        CheckConstraint(
            "attempt >= 1 AND max_attempts >= 1 AND attempt <= max_attempts",
            name="ck_background_task_attempt_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    task_type: Mapped[BackgroundTaskType] = mapped_column(
        Enum(BackgroundTaskType),
        index=True,
    )
    status: Mapped[BackgroundTaskStatus] = mapped_column(
        Enum(BackgroundTaskStatus),
        default=BackgroundTaskStatus.WAITING,
        server_default=BackgroundTaskStatus.WAITING.name,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255))
    source_task_id: Mapped[int | None] = mapped_column(Integer)
    parent_task_id: Mapped[int | None] = mapped_column(
        ForeignKey("background_tasks.id", ondelete="SET NULL"),
        index=True,
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        index=True,
    )
    progress: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    processed_items: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
    )
    total_items: Mapped[int | None] = mapped_column(Integer)
    attempt: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    max_attempts: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    cancellable: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="1",
    )
    pause_supported: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="0",
    )
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="0",
    )
    worker_id: Mapped[str | None] = mapped_column(String(255), index=True)
    task_payload: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    task_result: Mapped[dict | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
