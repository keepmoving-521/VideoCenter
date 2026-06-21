from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from videocenter.core.database import Base


class HlsTaskStatus(StrEnum):
    WAITING = "waiting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class HlsTask(Base):
    __tablename__ = "hls_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("local_resources.id", ondelete="CASCADE"),
        index=True,
    )
    status: Mapped[HlsTaskStatus] = mapped_column(
        Enum(HlsTaskStatus),
        default=HlsTaskStatus.WAITING,
        index=True,
    )
    progress: Mapped[float] = mapped_column(Float, default=0, server_default="0")
    output_directory: Mapped[str | None] = mapped_column(String(2048))
    playlist_path: Mapped[str | None] = mapped_column(String(2048))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
