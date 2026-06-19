from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from videocenter.core.database import Base


class MediaType(StrEnum):
    MOVIE = "movie"
    SERIES = "series"
    DOCUMENTARY = "documentary"
    ANIMATION = "animation"
    VARIETY_SHOW = "variety_show"
    SHORT_FILM = "short_film"
    OTHER = "other"


class MediaStatus(StrEnum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    AVAILABLE = "available"
    MISSING = "missing"
    ARCHIVED = "archived"


class Media(Base):
    __tablename__ = "media"
    __table_args__ = (
        CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes > 0",
            name="ck_media_duration_positive",
        ),
        CheckConstraint(
            "rating IS NULL OR (rating >= 0 AND rating <= 10)",
            name="ck_media_rating_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    sort_title: Mapped[str | None] = mapped_column(String(255), index=True)
    original_title: Mapped[str | None] = mapped_column(String(255))
    alternative_titles: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        server_default="[]",
    )
    media_type: Mapped[MediaType] = mapped_column(
        Enum(MediaType), default=MediaType.MOVIE, index=True
    )
    status: Mapped[MediaStatus] = mapped_column(
        Enum(MediaStatus),
        default=MediaStatus.PENDING,
        server_default=MediaStatus.PENDING.name,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text)
    release_year: Mapped[int | None] = mapped_column(Integer)
    release_date: Mapped[date | None] = mapped_column(Date)
    content_rating: Mapped[str | None] = mapped_column(String(32))
    source_site: Mapped[str | None] = mapped_column(String(100), index=True)
    source_page_url: Mapped[str | None] = mapped_column(String(2048))
    directors: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    actors: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    regions: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    languages: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    genres: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    rating: Mapped[float | None] = mapped_column(Float)
    poster_url: Mapped[str | None] = mapped_column(String(2048))
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
