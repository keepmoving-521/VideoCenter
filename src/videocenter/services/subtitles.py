import hashlib
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from videocenter.core.config import get_settings
from videocenter.services.media_artwork import MEDIA_CACHE_DIRECTORY_NAME

SUBTITLE_EXTENSIONS = {".vtt", ".srt", ".ass", ".ssa"}
SUBTITLE_CONVERSION_TIMEOUT_SECONDS = 30
_SRT_TIMING_PATTERN = re.compile(
    r"(?m)^(\d{2}:\d{2}:\d{2}),(\d{3})\s*-->\s*"
    r"(\d{2}:\d{2}:\d{2}),(\d{3})(.*)$"
)


@dataclass(frozen=True, slots=True)
class ExternalSubtitle:
    subtitle_id: str
    path: Path
    file_name: str
    format: str
    language: str | None


def discover_external_subtitles(video_path: Path) -> list[ExternalSubtitle]:
    if not video_path.parent.is_dir():
        return []
    prefix = video_path.stem.casefold()
    subtitles: list[ExternalSubtitle] = []
    for candidate in sorted(video_path.parent.iterdir(), key=lambda path: path.name.casefold()):
        suffix = candidate.suffix.casefold()
        candidate_stem = candidate.stem.casefold()
        if (
            not candidate.is_file()
            or suffix not in SUBTITLE_EXTENSIONS
            or candidate_stem != prefix
            and not candidate_stem.startswith(f"{prefix}.")
        ):
            continue
        subtitles.append(
            ExternalSubtitle(
                subtitle_id=_subtitle_id(candidate),
                path=candidate.resolve(),
                file_name=candidate.name,
                format=suffix.removeprefix("."),
                language=_subtitle_language(video_path, candidate),
            )
        )
    return subtitles


def get_external_subtitle(video_path: Path, subtitle_id: str) -> ExternalSubtitle | None:
    return next(
        (
            subtitle
            for subtitle in discover_external_subtitles(video_path)
            if subtitle.subtitle_id == subtitle_id
        ),
        None,
    )


def subtitle_as_webvtt(subtitle: ExternalSubtitle) -> Path:
    if subtitle.format == "vtt":
        return subtitle.path
    cache_path = _subtitle_cache_path(subtitle)
    if cache_path.is_file() and cache_path.stat().st_mtime_ns >= subtitle.path.stat().st_mtime_ns:
        return cache_path
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = cache_path.with_suffix(".tmp.vtt")
    temporary_path.unlink(missing_ok=True)
    if subtitle.format == "srt":
        _convert_srt_to_webvtt(subtitle.path, temporary_path)
    else:
        _convert_with_ffmpeg(subtitle.path, temporary_path)
    temporary_path.replace(cache_path)
    return cache_path


def _convert_srt_to_webvtt(source: Path, target: Path) -> None:
    content = source.read_text(encoding="utf-8-sig", errors="replace")
    converted = _SRT_TIMING_PATTERN.sub(
        r"\1.\2 --> \3.\4\5",
        content.replace("\r\n", "\n").replace("\r", "\n"),
    )
    target.write_text(f"WEBVTT\n\n{converted.lstrip()}", encoding="utf-8")


def _convert_with_ffmpeg(source: Path, target: Path) -> None:
    settings = get_settings()
    if settings.ffmpeg_path is None:
        executable = shutil.which("ffmpeg")
    else:
        candidate = Path(settings.ffmpeg_path).expanduser()
        executable = str(candidate.resolve()) if candidate.is_file() else None
    if executable is None:
        raise RuntimeError("FFmpeg 不可用，无法转换该字幕格式")
    result = subprocess.run(
        [
            executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-f",
            "webvtt",
            "-y",
            str(target),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=SUBTITLE_CONVERSION_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0 or not target.is_file():
        target.unlink(missing_ok=True)
        raise RuntimeError(result.stderr.strip() or "字幕格式转换失败")


def _subtitle_cache_path(subtitle: ExternalSubtitle) -> Path:
    settings = get_settings()
    return (
        settings.media_root
        / MEDIA_CACHE_DIRECTORY_NAME
        / "subtitles"
        / subtitle.subtitle_id[:2]
        / f"{subtitle.subtitle_id}.vtt"
    )


def _subtitle_id(path: Path) -> str:
    return hashlib.sha256(str(path.resolve()).casefold().encode()).hexdigest()[:24]


def _subtitle_language(video_path: Path, subtitle_path: Path) -> str | None:
    remainder = subtitle_path.stem[len(video_path.stem) :].strip(". _-")
    if not remainder:
        return None
    return re.split(r"[._]+", remainder, maxsplit=1)[0] or None
