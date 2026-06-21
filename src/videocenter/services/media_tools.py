import re
import shutil
import subprocess
from pathlib import Path

from videocenter.core.config import Settings, get_settings
from videocenter.schemas.system import MediaToolsStatus, MediaToolStatus

MEDIA_TOOL_TIMEOUT_SECONDS = 5
_VERSION_PATTERN = re.compile(r"\bversion\s+([^\s]+)", re.IGNORECASE)


def detect_media_tools(settings: Settings | None = None) -> MediaToolsStatus:
    settings = settings or get_settings()
    ffmpeg = detect_media_tool("ffmpeg", settings.ffmpeg_path)
    ffprobe = detect_media_tool("ffprobe", settings.ffprobe_path)
    return MediaToolsStatus(
        available=ffmpeg.available and ffprobe.available,
        ffmpeg=ffmpeg,
        ffprobe=ffprobe,
    )


def detect_media_tool(name: str, configured_path: str | None) -> MediaToolStatus:
    executable_path = _resolve_executable(name, configured_path)
    if executable_path is None:
        source = f"配置路径不存在：{configured_path}" if configured_path else "未在 PATH 中找到"
        return MediaToolStatus(
            name=name,
            available=False,
            configured_path=configured_path,
            executable_path=None,
            version=None,
            error=source,
        )

    try:
        result = subprocess.run(
            [executable_path, "-version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=MEDIA_TOOL_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _failed_status(name, configured_path, executable_path, "版本检测超时")
    except OSError as exc:
        return _failed_status(name, configured_path, executable_path, str(exc))

    output = (result.stdout or result.stderr).strip()
    first_line = output.splitlines()[0] if output else ""
    if result.returncode != 0:
        error = first_line or f"进程退出码：{result.returncode}"
        return _failed_status(name, configured_path, executable_path, error)

    match = _VERSION_PATTERN.search(first_line)
    return MediaToolStatus(
        name=name,
        available=True,
        configured_path=configured_path,
        executable_path=executable_path,
        version=match.group(1) if match else first_line or None,
        error=None,
    )


def _resolve_executable(name: str, configured_path: str | None) -> str | None:
    if configured_path is None:
        return shutil.which(name)
    candidate = Path(configured_path).expanduser()
    if not candidate.is_file():
        return None
    return str(candidate.resolve())


def _failed_status(
    name: str,
    configured_path: str | None,
    executable_path: str,
    error: str,
) -> MediaToolStatus:
    return MediaToolStatus(
        name=name,
        available=False,
        configured_path=configured_path,
        executable_path=executable_path,
        version=None,
        error=error,
    )
