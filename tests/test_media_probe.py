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


def test_probe_video_file_extracts_audio_tracks_and_embedded_subtitles(
    tmp_path,
    monkeypatch,
):
    video = tmp_path / "multilingual.mkv"
    video.write_bytes(b"video")
    monkeypatch.setattr(
        "videocenter.services.media_probe.resolve_ffprobe_executable",
        lambda settings=None: "ffprobe",
    )
    payload = {
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": "hevc",
                "width": 1920,
                "height": 1080,
            },
            {
                "index": 1,
                "codec_type": "audio",
                "codec_name": "aac",
                "channels": 2,
                "channel_layout": "stereo",
                "tags": {"language": "chi", "title": "中文"},
                "disposition": {"default": 1},
            },
            {
                "index": 2,
                "codec_type": "audio",
                "codec_name": "eac3",
                "channels": 6,
                "channel_layout": "5.1(side)",
                "tags": {"language": "eng"},
                "disposition": {"default": 0},
            },
            {
                "index": 3,
                "codec_type": "subtitle",
                "codec_name": "ass",
                "tags": {"language": "chi", "title": "简体中文"},
                "disposition": {"default": 1, "forced": 0},
            },
            {
                "index": 4,
                "codec_type": "subtitle",
                "codec_name": "subrip",
                "tags": {"language": "eng"},
                "disposition": {"default": 0, "forced": 1},
            },
        ],
        "format": {"duration": "120"},
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

    assert info.audio_codec == "aac"
    assert len(info.audio_tracks) == 2
    assert info.audio_tracks[0].channels == 2
    assert info.audio_tracks[0].channel_layout == "stereo"
    assert info.audio_tracks[0].language == "chi"
    assert info.audio_tracks[0].is_default is True
    assert info.audio_tracks[1].codec == "eac3"
    assert info.audio_tracks[1].channels == 6
    assert len(info.subtitle_tracks) == 2
    assert info.subtitle_tracks[0].title == "简体中文"
    assert info.subtitle_tracks[0].is_default is True
    assert info.subtitle_tracks[1].is_forced is True


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
