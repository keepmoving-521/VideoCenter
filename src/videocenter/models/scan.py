from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from videocenter.core.database import Base


class ScanTaskStatus(StrEnum):
    WAITING = "waiting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScanTask(Base):
    __tablename__ = "scan_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(String(2048))
    media_id: Mapped[int | None] = mapped_column(
        ForeignKey("media.id", ondelete="SET NULL"),
        index=True,
    )
    incremental: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="1",
    )
    status: Mapped[ScanTaskStatus] = mapped_column(
        Enum(ScanTaskStatus),
        default=ScanTaskStatus.WAITING,
        index=True,
    )
    progress: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    total_files: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    processed_files: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    discovered_files: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    added_files: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    updated_files: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    skipped_files: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
