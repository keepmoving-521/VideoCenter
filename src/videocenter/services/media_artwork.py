import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from videocenter.core.config import Settings, get_settings

logger = logging.getLogger(__name__)
MEDIA_CACHE_DIRECTORY_NAME = ".videocenter-cache"
ARTWORK_TIMEOUT_SECONDS = 60
PREVIEW_COUNT = 3


@dataclass(frozen=True, slots=True)
class GeneratedVideoArtwork:
    cover_image_path: str
    preview_thumbnail_paths: tuple[str, ...]


def generate_video_artwork(
    video_path: Path,
    *,
    checksum_sha256: str,
    duration_seconds: float | None,
    settings: Settings | None = None,
) -> GeneratedVideoArtwork | None:
    settings = settings or get_settings()
    executable = resolve_ffmpeg_executable(settings)
    if executable is None:
        return None

    output_directory = (
        settings.media_root / MEDIA_CACHE_DIRECTORY_NAME / "artwork" / checksum_sha256[:2]
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    cover_path = output_directory / f"{checksum_sha256}-cover.jpg"
    preview_paths = tuple(
        output_directory / f"{checksum_sha256}-preview-{index:02d}.jpg"
        for index in range(1, PREVIEW_COUNT + 1)
    )
    cover_time, preview_times = _capture_times(duration_seconds)

    if not _generate_frame(
        executable,
        video_path=video_path,
        output_path=cover_path,
        capture_time=cover_time,
        width=1280,
    ):
        return None

    generated_previews: list[Path] = []
    for output_path, capture_time in zip(preview_paths, preview_times, strict=True):
        if _generate_frame(
            executable,
            video_path=video_path,
            output_path=output_path,
            capture_time=capture_time,
            width=480,
        ):
            generated_previews.append(output_path)

    return GeneratedVideoArtwork(
        cover_image_path=str(cover_path.resolve()),
        preview_thumbnail_paths=tuple(str(path.resolve()) for path in generated_previews),
    )


def resolve_ffmpeg_executable(settings: Settings | None = None) -> str | None:
    settings = settings or get_settings()
    if settings.ffmpeg_path is None:
        return shutil.which("ffmpeg")
    candidate = Path(settings.ffmpeg_path).expanduser()
    return str(candidate.resolve()) if candidate.is_file() else None


def _generate_frame(
    executable: str,
    *,
    video_path: Path,
    output_path: Path,
    capture_time: float,
    width: int,
) -> bool:
    if output_path.is_file():
        return True
    temporary_path = output_path.with_name(f"{output_path.stem}.tmp{output_path.suffix}")
    temporary_path.unlink(missing_ok=True)
    try:
        result = subprocess.run(
            [
                executable,
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{capture_time:.3f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-vf",
                f"scale={width}:-2",
                "-q:v",
                "3",
                "-y",
                str(temporary_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=ARTWORK_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("FFmpeg thumbnail generation failed for %s: %s", video_path, exc)
        temporary_path.unlink(missing_ok=True)
        return False
    if result.returncode != 0 or not temporary_path.is_file():
        logger.warning(
            "FFmpeg thumbnail generation failed for %s: %s",
            video_path,
            result.stderr.strip() or f"exit code {result.returncode}",
        )
        temporary_path.unlink(missing_ok=True)
        return False
    temporary_path.replace(output_path)
    return True


def _capture_times(duration_seconds: float | None) -> tuple[float, tuple[float, ...]]:
    if duration_seconds is None or duration_seconds <= 0:
        return 1.0, (1.0, 5.0, 10.0)
    safe_duration = max(duration_seconds - 0.25, 0.0)
    cover_time = min(duration_seconds * 0.1, safe_duration)
    preview_times = tuple(
        min(duration_seconds * fraction, safe_duration) for fraction in (0.25, 0.5, 0.75)
    )
    return cover_time, preview_times
