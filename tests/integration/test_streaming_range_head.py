from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from videocenter.models.media import MediaStatus

pytestmark = pytest.mark.integration


def test_streaming_get_supports_full_and_single_ranges(
    api_client: TestClient,
    model_factory,
):
    path = Path("data/media/range-test.mp4").resolve()
    content = b"0123456789"
    path.write_bytes(content)
    resource = model_factory.local_resource(
        file_path=str(path),
        file_name=path.name,
        file_size=len(content),
    )

    try:
        full = api_client.get(f"/api/v1/stream/{resource.id}")
        assert full.status_code == 200
        assert full.content == content
        assert full.headers["accept-ranges"] == "bytes"
        assert full.headers["content-length"] == "10"
        assert full.headers["etag"]
        assert full.headers["last-modified"]
        assert full.headers["cache-control"] == "private, max-age=3600, no-transform"

        fixed = api_client.get(
            f"/api/v1/stream/{resource.id}",
            headers={"Range": "bytes=2-5"},
        )
        assert fixed.status_code == 206
        assert fixed.content == b"2345"
        assert fixed.headers["content-range"] == "bytes 2-5/10"
        assert fixed.headers["content-length"] == "4"

        opened = api_client.get(
            f"/api/v1/stream/{resource.id}",
            headers={"Range": "bytes=7-"},
        )
        assert opened.status_code == 206
        assert opened.content == b"789"
        assert opened.headers["content-range"] == "bytes 7-9/10"

        suffix = api_client.get(
            f"/api/v1/stream/{resource.id}",
            headers={"Range": "bytes=-4"},
        )
        assert suffix.status_code == 206
        assert suffix.content == b"6789"
        assert suffix.headers["content-range"] == "bytes 6-9/10"

        clamped = api_client.get(
            f"/api/v1/stream/{resource.id}",
            headers={"Range": "bytes=8-999"},
        )
        assert clamped.status_code == 206
        assert clamped.content == b"89"
        assert clamped.headers["content-range"] == "bytes 8-9/10"
    finally:
        path.unlink(missing_ok=True)


@pytest.mark.parametrize(
    "range_header",
    [
        "bytes=10-",
        "bytes=5-2",
        "bytes=0-2,5-7",
        "items=0-2",
        "bytes=-",
    ],
)
def test_streaming_invalid_range_returns_416(
    api_client: TestClient,
    model_factory,
    range_header: str,
):
    path = Path("data/media/invalid-range-test.mp4").resolve()
    path.write_bytes(b"0123456789")
    resource = model_factory.local_resource(
        file_path=str(path),
        file_name=path.name,
        file_size=10,
    )

    try:
        response = api_client.get(
            f"/api/v1/stream/{resource.id}",
            headers={"Range": range_header},
        )
        assert response.status_code == 416
        assert response.headers["accept-ranges"] == "bytes"
        assert response.headers["content-range"] == "bytes */10"
        assert response.json()["error"]["code"] == "INVALID_BYTE_RANGE"
    finally:
        path.unlink(missing_ok=True)


def test_video_head_returns_get_metadata_without_body(
    api_client: TestClient,
    model_factory,
):
    path = Path("data/media/head-test.mkv").resolve()
    path.write_bytes(b"abcdefghij")
    resource = model_factory.local_resource(
        file_path=str(path),
        file_name=path.name,
        file_size=10,
        mime_type="video/x-matroska",
    )

    try:
        full = api_client.head(f"/api/v1/stream/{resource.id}")
        assert full.status_code == 200
        assert full.content == b""
        assert full.headers["content-length"] == "10"
        assert full.headers["content-type"].startswith("video/x-matroska")
        assert full.headers["accept-ranges"] == "bytes"
        assert full.headers["etag"]
        assert full.headers["last-modified"]

        partial = api_client.head(
            f"/api/v1/stream/{resource.id}",
            headers={"Range": "bytes=3-6"},
        )
        assert partial.status_code == 206
        assert partial.content == b""
        assert partial.headers["content-length"] == "4"
        assert partial.headers["content-range"] == "bytes 3-6/10"
        assert partial.headers["etag"] == full.headers["etag"]
    finally:
        path.unlink(missing_ok=True)


def test_video_cache_conditional_requests_return_304(
    api_client: TestClient,
    model_factory,
):
    path = Path("data/media/cache-test.mp4").resolve()
    path.write_bytes(b"cache-content")
    resource = model_factory.local_resource(
        file_path=str(path),
        file_name=path.name,
        file_size=path.stat().st_size,
    )

    try:
        initial = api_client.get(f"/api/v1/stream/{resource.id}")
        etag = initial.headers["etag"]
        last_modified = initial.headers["last-modified"]

        by_etag = api_client.get(
            f"/api/v1/stream/{resource.id}",
            headers={"If-None-Match": etag},
        )
        assert by_etag.status_code == 304
        assert by_etag.content == b""
        assert by_etag.headers["etag"] == etag
        assert by_etag.headers["cache-control"] == "private, max-age=3600, no-transform"

        by_date = api_client.head(
            f"/api/v1/stream/{resource.id}",
            headers={"If-Modified-Since": last_modified},
        )
        assert by_date.status_code == 304
        assert by_date.content == b""

        ranged = api_client.get(
            f"/api/v1/stream/{resource.id}",
            headers={"Range": "bytes=0-4", "If-None-Match": etag},
        )
        assert ranged.status_code == 206
        assert ranged.content == b"cache"
    finally:
        path.unlink(missing_ok=True)


def test_missing_video_is_marked_unavailable_and_media_status_updated(
    api_client: TestClient,
    db_session,
    model_factory,
):
    media = model_factory.media(status=MediaStatus.AVAILABLE)
    resource = model_factory.local_resource(
        media=media,
        file_path=str(Path("data/media/lost-playback.mp4").resolve()),
        is_available=True,
    )

    response = api_client.get(f"/api/v1/stream/{resource.id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "VIDEO_FILE_MISSING"
    db_session.refresh(resource)
    db_session.refresh(media)
    assert resource.is_available is False
    assert resource.missing_at is not None
    assert media.status == MediaStatus.MISSING


def test_playback_resource_detail_returns_urls_and_detects_missing_file(
    api_client: TestClient,
    db_session,
    model_factory,
):
    path = Path("data/media/playback-detail.mp4").resolve()
    path.write_bytes(b"video")
    resource = model_factory.local_resource(
        file_path=str(path),
        file_name=path.name,
        file_size=5,
        duration_seconds=120,
        video_width=1920,
        video_height=1080,
        video_codec="h264",
        audio_codec="aac",
        cover_image_path="cover.jpg",
        preview_thumbnail_paths=["one.jpg", "two.jpg"],
    )

    try:
        response = api_client.get(f"/api/v1/stream/{resource.id}/details")
        assert response.status_code == 200
        payload = response.json()
        assert payload["playable"] is True
        assert payload["file_exists"] is True
        assert payload["stream_url"] == f"/api/v1/stream/{resource.id}"
        assert payload["head_url"] == f"/api/v1/stream/{resource.id}"
        assert payload["cover_url"] == f"/api/v1/local-resources/{resource.id}/cover"
        assert payload["preview_urls"] == [
            f"/api/v1/local-resources/{resource.id}/previews/0",
            f"/api/v1/local-resources/{resource.id}/previews/1",
        ]
        assert payload["resource"]["duration_seconds"] == 120

        path.unlink()
        missing = api_client.get(f"/api/v1/stream/{resource.id}/details").json()
        assert missing["playable"] is False
        assert missing["file_exists"] is False
        assert missing["resource"]["is_available"] is False
        db_session.refresh(resource)
        assert resource.missing_at is not None
    finally:
        path.unlink(missing_ok=True)


def test_empty_video_head_and_range(
    api_client: TestClient,
    model_factory,
):
    path = Path("data/media/empty-head-test.mp4").resolve()
    path.write_bytes(b"")
    resource = model_factory.local_resource(
        file_path=str(path),
        file_name=path.name,
        file_size=0,
    )

    try:
        head = api_client.head(f"/api/v1/stream/{resource.id}")
        assert head.status_code == 200
        assert head.headers["content-length"] == "0"

        ranged = api_client.get(
            f"/api/v1/stream/{resource.id}",
            headers={"Range": "bytes=0-"},
        )
        assert ranged.status_code == 416
        assert ranged.headers["content-range"] == "bytes */0"
    finally:
        path.unlink(missing_ok=True)


def test_video_head_not_found(
    api_client: TestClient,
):
    response = api_client.head("/api/v1/stream/999999")

    assert response.status_code == 404
    assert response.content == b""
    assert response.headers["x-request-id"]
