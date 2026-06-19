from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from videocenter.core.database import Base


class MediaType(StrEnum):
    MOVIE = "movie"
    SERIES = "series"
    OTHER = "other"


class Media(Base):
    __tablename__ = "media"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    original_title: Mapped[str | None] = mapped_column(String(255))
    media_type: Mapped[MediaType] = mapped_column(
        Enum(MediaType), default=MediaType.MOVIE, index=True
    )
    description: Mapped[str | None] = mapped_column(Text)
    release_year: Mapped[int | None] = mapped_column(Integer)
    poster_url: Mapped[str | None] = mapped_column(String(2048))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    resources: Mapped[list["LocalResource"]] = relationship(
        back_populates="media", cascade="all, delete-orphan"
    )


class LocalResource(Base):
    __tablename__ = "local_resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    media_id: Mapped[int | None] = mapped_column(
        ForeignKey("media.id", ondelete="SET NULL"), index=True
    )
    file_path: Mapped[str] = mapped_column(String(2048), unique=True)
    file_name: Mapped[str] = mapped_column(String(512))
    file_size: Mapped[int] = mapped_column(Integer)
    mime_type: Mapped[str] = mapped_column(String(128), default="video/mp4")
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    media: Mapped[Media | None] = relationship(back_populates="resources")
