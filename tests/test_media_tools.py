import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from videocenter.core.config import Settings
from videocenter.services.media_tools import detect_media_tool, detect_media_tools


def test_media_tools_are_detected_from_system_path(monkeypatch):
    paths = {
        "ffmpeg": "C:/tools/ffmpeg.exe",
        "ffprobe": "C:/tools/ffprobe.exe",
    }
    monkeypatch.setattr(
        "videocenter.services.media_tools.shutil.which",
        paths.get,
    )

    def fake_run(command, **kwargs):
        del kwargs
        name = Path(command[0]).stem
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=f"{name} version 7.1.2 Copyright",
            stderr="",
        )

    monkeypatch.setattr("videocenter.services.media_tools.subprocess.run", fake_run)

    status = detect_media_tools(Settings(_env_file=None))

    assert status.available is True
    assert status.ffmpeg.available is True
    assert status.ffmpeg.executable_path == paths["ffmpeg"]
    assert status.ffmpeg.version == "7.1.2"
    assert status.ffprobe.version == "7.1.2"


def test_configured_media_tool_path_takes_priority(tmp_path, monkeypatch):
    executable = tmp_path / "custom-ffmpeg.exe"
    executable.write_bytes(b"executable")
    monkeypatch.setattr(
        "videocenter.services.media_tools.shutil.which",
        lambda name: "C:/wrong/path.exe",
    )
    monkeypatch.setattr(
        "videocenter.services.media_tools.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            0,
            stdout="ffmpeg version 6.0-custom",
            stderr="",
        ),
    )

    status = detect_media_tool("ffmpeg", str(executable))

    assert status.available is True
    assert status.configured_path == str(executable)
    assert status.executable_path == str(executable.resolve())
    assert status.version == "6.0-custom"


def test_missing_configured_media_tool_reports_error(tmp_path):
    configured_path = str(tmp_path / "missing-ffprobe.exe")

    status = detect_media_tool("ffprobe", configured_path)

    assert status.available is False
    assert status.configured_path == configured_path
    assert status.executable_path is None
    assert configured_path in status.error


def test_media_tool_timeout_is_reported(monkeypatch):
    monkeypatch.setattr(
        "videocenter.services.media_tools.shutil.which",
        lambda name: name,
    )

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr("videocenter.services.media_tools.subprocess.run", timeout)

    status = detect_media_tool("ffmpeg", None)

    assert status.available is False
    assert status.error == "版本检测超时"


def test_media_tools_status_route(api_client: TestClient, monkeypatch):
    monkeypatch.setattr(
        "videocenter.api.routes.system.detect_media_tools",
        lambda: {
            "available": False,
            "ffmpeg": {
                "name": "ffmpeg",
                "available": True,
                "configured_path": None,
                "executable_path": "ffmpeg",
                "version": "7.1",
                "error": None,
            },
            "ffprobe": {
                "name": "ffprobe",
                "available": False,
                "configured_path": None,
                "executable_path": None,
                "version": None,
                "error": "未在 PATH 中找到",
            },
        },
    )

    response = api_client.get("/api/v1/system/media-tools")

    assert response.status_code == 200
    assert response.json()["available"] is False
    assert response.json()["ffmpeg"]["version"] == "7.1"
