import subprocess
from pathlib import Path

from videocenter.services.subtitles import (
    discover_external_subtitles,
    get_external_subtitle,
    subtitle_as_webvtt,
)


def test_discover_external_subtitles_matches_video_sidecars(tmp_path):
    video = tmp_path / "Movie.Title.mp4"
    video.write_bytes(b"video")
    (tmp_path / "Movie.Title.zh-CN.srt").write_text("subtitle", encoding="utf-8")
    (tmp_path / "Movie.Title.en.vtt").write_text("WEBVTT", encoding="utf-8")
    (tmp_path / "Other.Movie.srt").write_text("other", encoding="utf-8")
    (tmp_path / "Movie.Title.txt").write_text("text", encoding="utf-8")

    subtitles = discover_external_subtitles(video)

    assert [item.file_name for item in subtitles] == [
        "Movie.Title.en.vtt",
        "Movie.Title.zh-CN.srt",
    ]
    assert [item.language for item in subtitles] == ["en", "zh-CN"]
    assert get_external_subtitle(video, subtitles[0].subtitle_id) == subtitles[0]
    assert get_external_subtitle(video, "unknown") is None


def test_srt_is_converted_to_webvtt(tmp_path, monkeypatch):
    media_root = tmp_path / "media"
    media_root.mkdir()
    video = media_root / "movie.mp4"
    video.write_bytes(b"video")
    subtitle_path = media_root / "movie.zh.srt"
    subtitle_path.write_text(
        "1\r\n00:00:01,250 --> 00:00:03,500\r\n你好\r\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("VIDEOCENTER_MEDIA_ROOT", str(media_root))
    from videocenter.core.config import get_settings

    get_settings.cache_clear()
    try:
        subtitle = discover_external_subtitles(video)[0]
        converted = subtitle_as_webvtt(subtitle)
        content = converted.read_text(encoding="utf-8")
        assert content.startswith("WEBVTT\n\n")
        assert "00:00:01.250 --> 00:00:03.500" in content
        assert "你好" in content
    finally:
        get_settings.cache_clear()


def test_ass_subtitle_uses_ffmpeg_conversion(tmp_path, monkeypatch):
    media_root = tmp_path / "media"
    media_root.mkdir()
    video = media_root / "movie.mkv"
    video.write_bytes(b"video")
    (media_root / "movie.ass").write_text("[Script Info]", encoding="utf-8")
    monkeypatch.setenv("VIDEOCENTER_MEDIA_ROOT", str(media_root))
    monkeypatch.setenv("VIDEOCENTER_FFMPEG_PATH", str(tmp_path / "ffmpeg.exe"))
    (tmp_path / "ffmpeg.exe").write_bytes(b"exe")
    from videocenter.core.config import get_settings

    get_settings.cache_clear()

    def fake_run(command, **kwargs):
        del kwargs
        Path(command[-1]).write_text("WEBVTT\n\nconverted", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("videocenter.services.subtitles.subprocess.run", fake_run)
    try:
        converted = subtitle_as_webvtt(discover_external_subtitles(video)[0])
        assert converted.read_text(encoding="utf-8") == "WEBVTT\n\nconverted"
    finally:
        get_settings.cache_clear()
