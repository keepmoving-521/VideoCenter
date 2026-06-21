import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from videocenter.core.config import Settings, get_settings

logger = logging.getLogger(__name__)
MEDIA_PROBE_TIMEOUT_SECONDS = 30


@dataclass(frozen=True, slots=True)
class VideoMediaInfo:
    duration_seconds: float | None
    width: int | None
    height: int | None
    video_codec: str | None
    bitrate: int | None


def probe_video_file(
    path: Path,
    settings: Settings | None = None,
) -> VideoMediaInfo | None:
    executable = resolve_ffprobe_executable(settings)
    if executable is None:
        return None
    try:
        result = subprocess.run(
            [
                executable,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "format=duration,bit_rate:stream=codec_name,width,height,duration,bit_rate",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=MEDIA_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("FFprobe media analysis failed for %s: %s", path, exc)
        return None
    if result.returncode != 0:
        logger.warning(
            "FFprobe media analysis failed for %s: %s",
            path,
            result.stderr.strip() or f"exit code {result.returncode}",
        )
        return None
    try:
        payload = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError):
        logger.warning("FFprobe returned invalid JSON for %s", path)
        return None

    stream = next(iter(payload.get("streams") or []), {})
    format_info = payload.get("format") or {}
    return VideoMediaInfo(
        duration_seconds=_first_positive_float(
            format_info.get("duration"),
            stream.get("duration"),
        ),
        width=_positive_int(stream.get("width")),
        height=_positive_int(stream.get("height")),
        video_codec=_clean_text(stream.get("codec_name")),
        bitrate=_first_positive_int(
            stream.get("bit_rate"),
            format_info.get("bit_rate"),
        ),
    )


def resolve_ffprobe_executable(settings: Settings | None = None) -> str | None:
    settings = settings or get_settings()
    if settings.ffprobe_path is None:
        return shutil.which("ffprobe")
    candidate = Path(settings.ffprobe_path).expanduser()
    return str(candidate.resolve()) if candidate.is_file() else None


def _positive_float(value) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _first_positive_float(*values) -> float | None:
    for value in values:
        parsed = _positive_float(value)
        if parsed is not None:
            return parsed
    return None


def _positive_int(value) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _first_positive_int(*values) -> int | None:
    for value in values:
        parsed = _positive_int(value)
        if parsed is not None:
            return parsed
    return None


def _clean_text(value) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
