from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from videocenter.core.config import AppEnvironment, Settings, get_settings


def test_environment_specific_file_overrides_common_file(monkeypatch):
    project_root = Path(__file__).resolve().parents[1]
    config_dir = project_root / "data" / f"config_test_{uuid4().hex}"
    config_dir.mkdir(parents=True)
    (config_dir / ".env").write_text(
        "VIDEOCENTER_APP_NAME=Common Name\nVIDEOCENTER_LOG_LEVEL=INFO\n",
        encoding="utf-8",
    )
    (config_dir / ".env.testing").write_text(
        "VIDEOCENTER_APP_NAME=Testing Name\nVIDEOCENTER_LOG_LEVEL=WARNING\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(config_dir)
    get_settings.cache_clear()
    try:
        settings = get_settings(AppEnvironment.TESTING)
        assert settings.environment == AppEnvironment.TESTING
        assert settings.app_name == "Testing Name"
        assert settings.log_level == "WARNING"
    finally:
        get_settings.cache_clear()
        monkeypatch.chdir(project_root)
        for path in config_dir.iterdir():
            path.unlink()
        config_dir.rmdir()


def test_environment_variable_has_highest_configuration_priority(monkeypatch):
    monkeypatch.setenv("VIDEOCENTER_APP_NAME", "Environment Name")
    get_settings.cache_clear()
    try:
        settings = get_settings(AppEnvironment.DEVELOPMENT)
        assert settings.app_name == "Environment Name"
    finally:
        get_settings.cache_clear()


def test_production_rejects_debug_mode():
    with pytest.raises(ValidationError, match="Debug mode must be disabled"):
        Settings(
            environment=AppEnvironment.PRODUCTION,
            debug=True,
            _env_file=None,
        )


def test_production_rejects_wildcard_cors():
    with pytest.raises(ValidationError, match="Wildcard CORS origins"):
        Settings(
            environment=AppEnvironment.PRODUCTION,
            cors_origins=["*"],
            _env_file=None,
        )


def test_parser_retry_settings_are_configurable():
    settings = Settings(
        parser_timeout_seconds=12,
        parser_max_attempts=4,
        parser_retry_delay_seconds=0.25,
        parser_retry_max_delay_seconds=2,
        parser_cache_enabled=False,
        parser_cache_ttl_seconds=120,
        parser_cache_max_entries=25,
        _env_file=None,
    )

    assert settings.parser_timeout_seconds == 12
    assert settings.parser_max_attempts == 4
    assert settings.parser_retry_delay_seconds == 0.25
    assert settings.parser_retry_max_delay_seconds == 2
    assert settings.parser_cache_enabled is False
    assert settings.parser_cache_ttl_seconds == 120
    assert settings.parser_cache_max_entries == 25


def test_download_worker_count_is_configurable():
    settings = Settings(download_worker_count=3, _env_file=None)

    assert settings.download_worker_count == 3


@pytest.mark.parametrize("worker_count", [0, 17])
def test_invalid_download_worker_count_is_rejected(worker_count):
    with pytest.raises(ValidationError):
        Settings(download_worker_count=worker_count, _env_file=None)


@pytest.mark.parametrize(
    "values",
    [
        {"parser_timeout_seconds": 0},
        {"parser_max_attempts": 0},
        {
            "parser_retry_delay_seconds": 2,
            "parser_retry_max_delay_seconds": 1,
        },
        {"parser_cache_ttl_seconds": 0},
        {"parser_cache_max_entries": 0},
    ],
)
def test_invalid_parser_retry_settings_are_rejected(values):
    with pytest.raises(ValidationError):
        Settings(**values, _env_file=None)
