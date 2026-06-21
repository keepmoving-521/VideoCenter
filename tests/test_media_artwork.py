import subprocess
from pathlib import Path

from videocenter.services.media_artwork import generate_video_artwork


def test_generate_video_artwork_creates_cover_and_previews(tmp_path, monkeypatch):
    media_root = tmp_path / "media"
    media_root.mkdir()
    video = media_root / "movie.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(
        "videocenter.services.media_artwork.resolve_ffmpeg_executable",
        lambda settings=None: "ffmpeg",
    )
    capture_times: list[float] = []

    def fake_run(command, **kwargs):
        del kwargs
        capture_times.append(float(command[command.index("-ss") + 1]))
        Path(command[-1]).write_bytes(b"jpeg")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(
        "videocenter.services.media_artwork.subprocess.run",
        fake_run,
    )
    from videocenter.core.config import Settings

    artwork = generate_video_artwork(
        video,
        checksum_sha256="a" * 64,
        duration_seconds=100,
        settings=Settings(media_root=media_root, _env_file=None),
    )

    assert artwork is not None
    assert Path(artwork.cover_image_path).read_bytes() == b"jpeg"
    assert len(artwork.preview_thumbnail_paths) == 3
    assert all(Path(path).read_bytes() == b"jpeg" for path in artwork.preview_thumbnail_paths)
    assert capture_times == [10.0, 25.0, 50.0, 75.0]


def test_generate_video_artwork_without_ffmpeg_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "videocenter.services.media_artwork.resolve_ffmpeg_executable",
        lambda settings=None: None,
    )

    assert (
        generate_video_artwork(
            tmp_path / "movie.mp4",
            checksum_sha256="b" * 64,
            duration_seconds=None,
        )
        is None
    )


def test_generate_video_artwork_fails_when_cover_fails(tmp_path, monkeypatch):
    video = tmp_path / "movie.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(
        "videocenter.services.media_artwork.resolve_ffmpeg_executable",
        lambda settings=None: "ffmpeg",
    )
    monkeypatch.setattr(
        "videocenter.services.media_artwork.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="failed",
        ),
    )

    assert (
        generate_video_artwork(
            video,
            checksum_sha256="c" * 64,
            duration_seconds=60,
        )
        is None
    )
