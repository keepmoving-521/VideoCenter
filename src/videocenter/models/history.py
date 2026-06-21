from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from videocenter.core.database import Base


class WatchHistory(Base):
    __tablename__ = "watch_history"
    __table_args__ = (UniqueConstraint("media_id", name="uq_history_media"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media.id"), index=True)
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("local_resources.id"))
    episode_id: Mapped[int | None] = mapped_column(
        ForeignKey("episodes.id", ondelete="SET NULL"),
        index=True,
    )
    position_seconds: Mapped[float] = mapped_column(Float, default=0)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="0",
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    watched_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), index=True
    )


class WatchDailyStat(Base):
    __tablename__ = "watch_daily_stats"
    __table_args__ = (UniqueConstraint("stat_date", "media_id", name="uq_watch_daily_date_media"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stat_date: Mapped[date] = mapped_column(Date, index=True)
    media_id: Mapped[int] = mapped_column(
        ForeignKey("media.id", ondelete="CASCADE"),
        index=True,
    )
    watched_seconds: Mapped[float] = mapped_column(
        Float,
        default=0,
        server_default="0",
    )
    completion_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
