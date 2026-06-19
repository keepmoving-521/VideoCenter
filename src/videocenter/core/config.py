import os
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LogFormat(StrEnum):
    TEXT = "text"
    JSON = "json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VIDEOCENTER_",
        extra="ignore",
    )

    environment: AppEnvironment = AppEnvironment.DEVELOPMENT
    app_name: str = "VideoCenter"
    debug: bool = False
    log_level: str = "INFO"
    log_format: LogFormat = LogFormat.TEXT
    log_file_enabled: bool = True
    log_dir: Path = Path("./data/logs")
    log_file_name: str = "videocenter.log"
    log_max_bytes: int = 10 * 1024 * 1024
    log_backup_count: int = 5
    docs_enabled: bool = True
    database_echo: bool = False
    database_url: str = "sqlite:///./data/videocenter.db"
    media_root: Path = Path("./data/media")
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("media_root", "log_dir", mode="after")
    @classmethod
    def resolve_path(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @field_validator("api_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("API prefix must start with '/'")
        return value.rstrip("/") or "/"

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError("Unsupported log level")
        return normalized

    @field_validator("log_file_name")
    @classmethod
    def validate_log_file_name(cls, value: str) -> str:
        if not value or Path(value).name != value:
            raise ValueError("Log file name must not contain a directory")
        return value

    @field_validator("log_max_bytes", "log_backup_count")
    @classmethod
    def validate_positive_log_rotation_value(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Log rotation values must be greater than zero")
        return value

    @model_validator(mode="after")
    def validate_environment_safety(self) -> "Settings":
        if self.environment == AppEnvironment.PRODUCTION:
            if self.debug:
                raise ValueError("Debug mode must be disabled in production")
            if "*" in self.cors_origins:
                raise ValueError("Wildcard CORS origins are not allowed in production")
        return self


def get_environment(value: AppEnvironment | str | None = None) -> AppEnvironment:
    if value is not None:
        return AppEnvironment(value)
    return AppEnvironment(os.getenv("VIDEOCENTER_ENVIRONMENT", AppEnvironment.DEVELOPMENT.value))


@lru_cache
def get_settings(environment: AppEnvironment | str | None = None) -> Settings:
    selected_environment = get_environment(environment)
    return Settings(
        environment=selected_environment,
        _env_file=(".env", f".env.{selected_environment.value}"),
        _env_file_encoding="utf-8",
    )
