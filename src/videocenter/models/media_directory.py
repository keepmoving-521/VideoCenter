from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from videocenter.core.database import Base


class MediaDirectory(Base):
    __tablename__ = "media_directories"
    __table_args__ = (
        CheckConstraint(
            "capacity_warning_threshold_percent >= 1 AND capacity_warning_threshold_percent <= 100",
            name="ck_media_directory_capacity_warning_threshold",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    path: Mapped[str] = mapped_column(String(2048), unique=True, index=True)
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="0",
        index=True,
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="1",
        index=True,
    )
    auto_scan: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="1",
    )
    capacity_warning_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="1",
    )
    capacity_warning_threshold_percent: Mapped[int] = mapped_column(
        Integer,
        default=90,
        server_default="90",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
