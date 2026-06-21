import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_subtitle_list_combines_embedded_and_external_tracks(
    api_client: TestClient,
    model_factory,
):
    root = Path("data/media/subtitle-list").resolve()
    root.mkdir(parents=True, exist_ok=True)
    video = root / "movie.mp4"
    video.write_bytes(b"video")
    srt = root / "movie.zh-CN.srt"
    srt.write_text(
        "1\n00:00:01,000 --> 00:00:02,000\n你好\n",
        encoding="utf-8",
    )
    vtt = root / "movie.en.vtt"
    vtt.write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nHello", encoding="utf-8")
    resource = model_factory.local_resource(
        file_path=str(video),
        file_name=video.name,
        embedded_subtitles=[
            {
                "stream_index": 3,
                "codec": "ass",
                "language": "chi",
                "title": "内嵌中文",
                "is_default": True,
                "is_forced": False,
            }
        ],
    )

    try:
        response = api_client.get(f"/api/v1/stream/{resource.id}/subtitles")
        assert response.status_code == 200
        payload = response.json()
        assert payload["resource_id"] == resource.id
        assert len(payload["subtitles"]) == 3
        embedded = payload["subtitles"][0]
        assert embedded["subtitle_id"] == "embedded-3"
        assert embedded["source"] == "embedded"
        assert embedded["access_url"] is None
        external = [item for item in payload["subtitles"] if item["source"] == "external"]
        assert {item["format"] for item in external} == {"srt", "vtt"}
        assert all(item["access_url"].endswith("?format=webvtt") for item in external)

        srt_item = next(item for item in external if item["format"] == "srt")
        converted = api_client.get(srt_item["access_url"])
        assert converted.status_code == 200
        assert converted.headers["content-type"].startswith("text/vtt")
        assert converted.text.startswith("WEBVTT")
        assert "00:00:01.000 --> 00:00:02.000" in converted.text

        vtt_item = next(item for item in external if item["format"] == "vtt")
        original = api_client.get(vtt_item["access_url"].replace("webvtt", "original"))
        assert original.status_code == 200
        assert original.text.startswith("WEBVTT")
    finally:
        video.unlink(missing_ok=True)
        srt.unlink(missing_ok=True)
        vtt.unlink(missing_ok=True)
        root.rmdir()
        shutil.rmtree(
            Path("data/media/.videocenter-cache/subtitles").resolve(),
            ignore_errors=True,
        )


def test_external_subtitle_access_is_scoped_to_video(
    api_client: TestClient,
    model_factory,
):
    root = Path("data/media/subtitle-security").resolve()
    root.mkdir(parents=True, exist_ok=True)
    video = root / "movie.mp4"
    video.write_bytes(b"video")
    unrelated = root / "other.srt"
    unrelated.write_text("secret", encoding="utf-8")
    resource = model_factory.local_resource(file_path=str(video), file_name=video.name)

    try:
        response = api_client.get(f"/api/v1/stream/{resource.id}/subtitles/not-a-valid-id")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "EXTERNAL_SUBTITLE_NOT_FOUND"
    finally:
        video.unlink(missing_ok=True)
        unrelated.unlink(missing_ok=True)
        root.rmdir()
