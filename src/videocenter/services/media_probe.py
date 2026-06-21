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
class AudioTrackInfo:
    stream_index: int
    codec: str | None
    language: str | None
    title: str | None
    channels: int | None
    channel_layout: str | None
    is_default: bool


@dataclass(frozen=True, slots=True)
class SubtitleTrackInfo:
    stream_index: int
    codec: str | None
    language: str | None
    title: str | None
    is_default: bool
    is_forced: bool


@dataclass(frozen=True, slots=True)
class VideoMediaInfo:
    duration_seconds: float | None
    width: int | None
    height: int | None
    video_codec: str | None
    bitrate: int | None
    audio_codec: str | None = None
    audio_tracks: tuple[AudioTrackInfo, ...] = ()
    subtitle_tracks: tuple[SubtitleTrackInfo, ...] = ()


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
                "-show_streams",
                "-show_format",
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

    streams = payload.get("streams") or []
    video_stream = next(
        (stream for stream in streams if stream.get("codec_type") == "video"),
        next(iter(streams), {}),
    )
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    subtitle_streams = [stream for stream in streams if stream.get("codec_type") == "subtitle"]
    format_info = payload.get("format") or {}
    audio_tracks = tuple(_audio_track(stream) for stream in audio_streams)
    subtitle_tracks = tuple(_subtitle_track(stream) for stream in subtitle_streams)
    return VideoMediaInfo(
        duration_seconds=_first_positive_float(
            format_info.get("duration"),
            video_stream.get("duration"),
        ),
        width=_positive_int(video_stream.get("width")),
        height=_positive_int(video_stream.get("height")),
        video_codec=_clean_text(video_stream.get("codec_name")),
        bitrate=_first_positive_int(
            video_stream.get("bit_rate"),
            format_info.get("bit_rate"),
        ),
        audio_codec=audio_tracks[0].codec if audio_tracks else None,
        audio_tracks=audio_tracks,
        subtitle_tracks=subtitle_tracks,
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


def _audio_track(stream: dict) -> AudioTrackInfo:
    tags = stream.get("tags") or {}
    disposition = stream.get("disposition") or {}
    return AudioTrackInfo(
        stream_index=_stream_index(stream),
        codec=_clean_text(stream.get("codec_name")),
        language=_clean_text(tags.get("language")),
        title=_clean_text(tags.get("title")),
        channels=_positive_int(stream.get("channels")),
        channel_layout=_clean_text(stream.get("channel_layout")),
        is_default=bool(disposition.get("default")),
    )


def _subtitle_track(stream: dict) -> SubtitleTrackInfo:
    tags = stream.get("tags") or {}
    disposition = stream.get("disposition") or {}
    return SubtitleTrackInfo(
        stream_index=_stream_index(stream),
        codec=_clean_text(stream.get("codec_name")),
        language=_clean_text(tags.get("language")),
        title=_clean_text(tags.get("title")),
        is_default=bool(disposition.get("default")),
        is_forced=bool(disposition.get("forced")),
    )


def _stream_index(stream: dict) -> int:
    try:
        return int(stream.get("index", 0))
    except (TypeError, ValueError):
        return 0
