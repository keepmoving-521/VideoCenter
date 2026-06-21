from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
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


media_tags = Table(
    "media_tags",
    Base.metadata,
    Column(
        "media_id",
        ForeignKey("media.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


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
        CheckConstraint(
            "personal_rating IS NULL OR (personal_rating >= 0 AND personal_rating <= 10)",
            name="ck_media_personal_rating_range",
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
    is_favorite: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="0",
        index=True,
    )
    personal_rating: Mapped[float | None] = mapped_column(Float)
    personal_notes: Mapped[str | None] = mapped_column(Text)
    poster_url: Mapped[str | None] = mapped_column(String(2048))
    background_url: Mapped[str | None] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    resources: Mapped[list["LocalResource"]] = relationship(back_populates="media")
    tags: Mapped[list["Tag"]] = relationship(
        secondary=media_tags,
        back_populates="media_items",
        order_by="Tag.name",
    )
    seasons: Mapped[list["Season"]] = relationship(
        back_populates="media",
        cascade="all, delete-orphan",
        order_by="Season.season_number",
    )


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    normalized_name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    media_items: Mapped[list[Media]] = relationship(
        secondary=media_tags,
        back_populates="tags",
    )


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = (
        UniqueConstraint("media_id", "season_number", name="uq_season_media_number"),
        CheckConstraint("season_number >= 0", name="ck_season_number_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    media_id: Mapped[int] = mapped_column(
        ForeignKey("media.id", ondelete="CASCADE"),
        index=True,
    )
    season_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    poster_url: Mapped[str | None] = mapped_column(String(2048))
    air_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    media: Mapped[Media] = relationship(back_populates="seasons")
    episodes: Mapped[list["Episode"]] = relationship(
        back_populates="season",
        cascade="all, delete-orphan",
        order_by="Episode.episode_number",
    )


class Episode(Base):
    __tablename__ = "episodes"
    __table_args__ = (
        UniqueConstraint(
            "season_id",
            "episode_number",
            name="uq_episode_season_number",
        ),
        CheckConstraint("episode_number > 0", name="ck_episode_number_positive"),
        CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes > 0",
            name="ck_episode_duration_positive",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"),
        index=True,
    )
    episode_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    air_date: Mapped[date | None] = mapped_column(Date)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    season: Mapped[Season] = relationship(back_populates="episodes")


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
    video_width: Mapped[int | None] = mapped_column(Integer)
    video_height: Mapped[int | None] = mapped_column(Integer)
    video_codec: Mapped[str | None] = mapped_column(String(100))
    bitrate: Mapped[int | None] = mapped_column(Integer)
    audio_codec: Mapped[str | None] = mapped_column(String(100))
    audio_tracks: Mapped[list[dict]] = mapped_column(
        JSON,
        default=list,
        server_default="[]",
    )
    embedded_subtitles: Mapped[list[dict]] = mapped_column(
        JSON,
        default=list,
        server_default="[]",
    )
    cover_image_path: Mapped[str | None] = mapped_column(String(2048))
    preview_thumbnail_paths: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        server_default="[]",
    )
    visual_assets_generated: Mapped[bool | None] = mapped_column(Boolean)
    media_info_probed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="0",
    )
    modified_at_ns: Mapped[int | None] = mapped_column(Integer)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    detected_media_type: Mapped[str | None] = mapped_column(String(30))
    parsed_title: Mapped[str | None] = mapped_column(String(255))
    parsed_release_year: Mapped[int | None] = mapped_column(Integer)
    parsed_season_number: Mapped[int | None] = mapped_column(Integer)
    parsed_episode_number: Mapped[int | None] = mapped_column(Integer)
    is_available: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="1",
        index=True,
    )
    missing_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    media: Mapped[Media | None] = relationship(back_populates="resources")
