from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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
