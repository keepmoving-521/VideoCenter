from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="VIDEOCENTER_",
        extra="ignore",
    )

    app_name: str = "VideoCenter"
    debug: bool = False
    database_url: str = "sqlite:///./data/videocenter.db"
    media_root: Path = Path("./data/media")
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("media_root", mode="after")
    @classmethod
    def resolve_media_root(cls, value: Path) -> Path:
        return value.expanduser().resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
