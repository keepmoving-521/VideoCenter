from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from videocenter.core.database import Base


class DownloadStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DownloadTask(Base):
    __tablename__ = "download_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    media_id: Mapped[int | None] = mapped_column(ForeignKey("media.id"), index=True)
    source_url: Mapped[str] = mapped_column(String(2048))
    target_name: Mapped[str] = mapped_column(String(512))
    target_path: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[DownloadStatus] = mapped_column(
        Enum(DownloadStatus), default=DownloadStatus.PENDING, index=True
    )
    progress: Mapped[float] = mapped_column(Float, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
