import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_audio_track_information_endpoint(
    api_client: TestClient,
    model_factory,
):
    resource = model_factory.local_resource(
        audio_codec="aac",
        audio_tracks=[
            {
                "stream_index": 1,
                "codec": "aac",
                "language": "zh-CN",
                "title": "中文立体声",
                "channels": 2,
                "channel_layout": "stereo",
                "is_default": True,
            },
            {
                "stream_index": 2,
                "codec": "eac3",
                "language": "en",
                "title": "English 5.1",
                "channels": 6,
                "channel_layout": "5.1(side)",
                "is_default": False,
            },
        ],
    )

    response = api_client.get(f"/api/v1/stream/{resource.id}/audio-tracks")

    assert response.status_code == 200
    payload = response.json()
    assert payload["resource_id"] == resource.id
    assert payload["default_stream_index"] == 1
    assert len(payload["tracks"]) == 2
    assert payload["tracks"][1]["channels"] == 6
    assert payload["tracks"][1]["channel_layout"] == "5.1(side)"


def test_video_quality_information_endpoint(
    api_client: TestClient,
    model_factory,
):
    resource = model_factory.local_resource(
        video_width=3840,
        video_height=2160,
        video_codec="hevc",
        bitrate=18_000_000,
    )

    response = api_client.get(f"/api/v1/stream/{resource.id}/quality")

    assert response.status_code == 200
    assert response.json() == {
        "resource_id": resource.id,
        "label": "4K",
        "width": 3840,
        "height": 2160,
        "aspect_ratio": "16:9",
        "pixel_count": 8_294_400,
        "bitrate": 18_000_000,
        "video_codec": "hevc",
    }


def test_browser_compatibility_endpoint_uses_user_agent(
    api_client: TestClient,
    model_factory,
):
    resource = model_factory.local_resource(
        file_name="movie.webm",
        mime_type="video/webm",
        video_codec="vp9",
        audio_codec="opus",
    )

    response = api_client.get(
        f"/api/v1/stream/{resource.id}/compatibility",
        headers={"User-Agent": "Mozilla/5.0 Firefox/126.0"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["browser_family"] == "firefox"
    assert payload["container"] == "webm"
    assert payload["status"] == "supported"
    assert payload["direct_play"] is True
    assert payload["can_play_type"] == "probably"


def test_playback_detail_contains_media_info_urls(
    api_client: TestClient,
    model_factory,
    tmp_path,
):
    video = tmp_path / "movie.mp4"
    video.write_bytes(b"video")
    resource = model_factory.local_resource(
        file_path=str(video),
        file_name=video.name,
    )

    payload = api_client.get(f"/api/v1/stream/{resource.id}/details").json()

    assert payload["audio_tracks_url"].endswith(f"/stream/{resource.id}/audio-tracks")
    assert payload["quality_url"].endswith(f"/stream/{resource.id}/quality")
    assert payload["compatibility_url"].endswith(f"/stream/{resource.id}/compatibility")
