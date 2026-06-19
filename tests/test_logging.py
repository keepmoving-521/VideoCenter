import json
import logging
from pathlib import Path
from uuid import uuid4

from videocenter.core.config import AppEnvironment, LogFormat, Settings
from videocenter.core.logging import build_logging_config, configure_logging


def test_build_logging_config_can_disable_file_handler():
    settings = Settings(
        environment=AppEnvironment.TESTING,
        log_file_enabled=False,
        _env_file=None,
    )

    config = build_logging_config(settings)

    assert set(config["handlers"]) == {"console"}
    assert config["root"]["handlers"] == ["console"]


def test_json_file_logging_contains_standard_context():
    project_root = Path(__file__).resolve().parents[1]
    log_dir = project_root / "data" / f"log_test_{uuid4().hex}"
    log_file = log_dir / "test.log"
    settings = Settings(
        environment=AppEnvironment.TESTING,
        log_level="INFO",
        log_format=LogFormat.JSON,
        log_file_enabled=True,
        log_dir=log_dir,
        log_file_name=log_file.name,
        _env_file=None,
    )
    root_logger = logging.getLogger()
    previous_handlers = root_logger.handlers[:]
    previous_level = root_logger.level

    try:
        configure_logging(settings)
        logging.getLogger("videocenter.test").info("日志测试", extra={"task_id": 42})
        for handler in root_logger.handlers:
            handler.flush()

        payload = json.loads(log_file.read_text(encoding="utf-8").splitlines()[-1])
        assert payload["level"] == "INFO"
        assert payload["logger"] == "videocenter.test"
        assert payload["environment"] == "testing"
        assert payload["message"] == "日志测试"
        assert payload["task_id"] == 42
    finally:
        for handler in root_logger.handlers:
            handler.close()
        root_logger.handlers = previous_handlers
        root_logger.setLevel(previous_level)
        log_file.unlink(missing_ok=True)
        log_dir.rmdir()
