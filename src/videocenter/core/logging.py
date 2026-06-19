import json
import logging
import logging.config
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from videocenter.core.config import Settings, get_settings

STANDARD_LOG_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
}


class EnvironmentFilter(logging.Filter):
    def __init__(self, environment: str) -> None:
        super().__init__()
        self.environment = environment

    def filter(self, record: logging.LogRecord) -> bool:
        record.environment = self.environment
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "environment": getattr(record, "environment", None),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in STANDARD_LOG_RECORD_FIELDS and key != "environment":
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def build_logging_config(settings: Settings) -> dict[str, Any]:
    formatter_name = settings.log_format.value
    handlers: dict[str, Any] = {
        "console": {
            "class": "logging.StreamHandler",
            "level": settings.log_level,
            "formatter": formatter_name,
            "filters": ["environment"],
            "stream": "ext://sys.stdout",
        }
    }
    root_handlers = ["console"]

    if settings.log_file_enabled:
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": settings.log_level,
            "formatter": formatter_name,
            "filters": ["environment"],
            "filename": str(settings.log_dir / settings.log_file_name),
            "maxBytes": settings.log_max_bytes,
            "backupCount": settings.log_backup_count,
            "encoding": "utf-8",
            "delay": True,
        }
        root_handlers.append("file")

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "environment": {
                "()": EnvironmentFilter,
                "environment": settings.environment.value,
            }
        },
        "formatters": {
            "text": {
                "format": (
                    "%(asctime)s | %(levelname)-8s | %(environment)s | "
                    "%(name)s | %(message)s"
                ),
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "json": {"()": JsonFormatter},
        },
        "handlers": handlers,
        "root": {
            "level": settings.log_level,
            "handlers": root_handlers,
        },
        "loggers": {
            "uvicorn": {"handlers": [], "propagate": True},
            "uvicorn.error": {"handlers": [], "propagate": True},
            "uvicorn.access": {"handlers": [], "propagate": True},
            "sqlalchemy.engine": {
                "handlers": [],
                "level": "INFO" if settings.database_echo else "WARNING",
                "propagate": True,
            },
        },
    }


def configure_logging(settings: Settings | None = None) -> None:
    selected_settings = settings or get_settings()
    if selected_settings.log_file_enabled:
        Path(selected_settings.log_dir).mkdir(parents=True, exist_ok=True)
    logging.config.dictConfig(build_logging_config(selected_settings))
