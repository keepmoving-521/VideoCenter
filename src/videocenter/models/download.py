from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from videocenter.core.database import Base


class DownloadStatus(StrEnum):
    WAITING = "waiting"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DownloadTask(Base):
    __tablename__ = "download_tasks"
    __table_args__ = (
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_download_progress_range"),
        CheckConstraint(
            "downloaded_bytes >= 0",
            name="ck_download_downloaded_bytes_non_negative",
        ),
        CheckConstraint(
            "total_bytes IS NULL OR total_bytes > 0",
            name="ck_download_total_bytes_positive",
        ),
        CheckConstraint(
            "speed_bytes_per_second IS NULL OR speed_bytes_per_second >= 0",
            name="ck_download_speed_non_negative",
        ),
        CheckConstraint(
            "remaining_seconds IS NULL OR remaining_seconds >= 0",
            name="ck_download_remaining_seconds_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    media_id: Mapped[int | None] = mapped_column(ForeignKey("media.id"), index=True)
    source_url: Mapped[str] = mapped_column(String(2048))
    target_name: Mapped[str] = mapped_column(String(512))
    target_path: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[DownloadStatus] = mapped_column(
        Enum(DownloadStatus), default=DownloadStatus.WAITING, index=True
    )
    progress: Mapped[float] = mapped_column(Float, default=0)
    downloaded_bytes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total_bytes: Mapped[int | None] = mapped_column(Integer)
    speed_bytes_per_second: Mapped[float | None] = mapped_column(Float)
    remaining_seconds: Mapped[float | None] = mapped_column(Float)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
