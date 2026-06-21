import json
import subprocess

from videocenter.services.media_probe import probe_video_file


def test_probe_video_file_extracts_media_information(tmp_path, monkeypatch):
    video = tmp_path / "movie.mkv"
    video.write_bytes(b"video")
    monkeypatch.setattr(
        "videocenter.services.media_probe.resolve_ffprobe_executable",
        lambda settings=None: "ffprobe",
    )
    payload = {
        "streams": [
            {
                "codec_name": "hevc",
                "width": 3840,
                "height": 2160,
                "bit_rate": "12000000",
            }
        ],
        "format": {
            "duration": "7321.456",
            "bit_rate": "12500000",
        },
    }
    monkeypatch.setattr(
        "videocenter.services.media_probe.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(payload),
            stderr="",
        ),
    )

    info = probe_video_file(video)

    assert info is not None
    assert info.duration_seconds == 7321.456
    assert info.width == 3840
    assert info.height == 2160
    assert info.video_codec == "hevc"
    assert info.bitrate == 12000000


def test_probe_video_file_uses_format_bitrate_and_stream_duration(
    tmp_path,
    monkeypatch,
):
    video = tmp_path / "movie.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(
        "videocenter.services.media_probe.resolve_ffprobe_executable",
        lambda settings=None: "ffprobe",
    )
    payload = {
        "streams": [
            {
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "duration": "60.5",
                "bit_rate": "N/A",
            }
        ],
        "format": {"bit_rate": "8000000"},
    }
    monkeypatch.setattr(
        "videocenter.services.media_probe.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(payload),
            stderr="",
        ),
    )

    info = probe_video_file(video)

    assert info.duration_seconds == 60.5
    assert info.bitrate == 8000000


def test_probe_video_file_failure_does_not_raise(tmp_path, monkeypatch):
    video = tmp_path / "broken.mp4"
    video.write_bytes(b"broken")
    monkeypatch.setattr(
        "videocenter.services.media_probe.resolve_ffprobe_executable",
        lambda settings=None: "ffprobe",
    )
    monkeypatch.setattr(
        "videocenter.services.media_probe.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="Invalid data",
        ),
    )

    assert probe_video_file(video) is None


def test_probe_video_file_without_ffprobe_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "videocenter.services.media_probe.resolve_ffprobe_executable",
        lambda settings=None: None,
    )

    assert probe_video_file(tmp_path / "movie.mp4") is None
