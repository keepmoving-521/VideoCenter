from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.support.api import ApiAssertions

pytestmark = pytest.mark.integration


def test_video_artwork_files_are_served(
    api_client: TestClient,
    model_factory,
):
    root = Path("data/media/.videocenter-cache/artwork/api-test").resolve()
    root.mkdir(parents=True, exist_ok=True)
    cover = root / "cover.jpg"
    preview = root / "preview.jpg"
    cover.write_bytes(b"cover-image")
    preview.write_bytes(b"preview-image")
    resource = model_factory.local_resource(
        cover_image_path=str(cover),
        preview_thumbnail_paths=[str(preview)],
        visual_assets_generated=True,
    )

    try:
        cover_response = api_client.get(f"/api/v1/local-resources/{resource.id}/cover")
        assert cover_response.status_code == 200
        assert cover_response.headers["content-type"] == "image/jpeg"
        assert cover_response.content == b"cover-image"

        preview_response = api_client.get(f"/api/v1/local-resources/{resource.id}/previews/0")
        assert preview_response.status_code == 200
        assert preview_response.content == b"preview-image"
    finally:
        cover.unlink(missing_ok=True)
        preview.unlink(missing_ok=True)
        root.rmdir()


def test_missing_video_artwork_returns_not_found(
    api_client: TestClient,
    api_assertions: ApiAssertions,
    model_factory,
):
    resource = model_factory.local_resource(
        cover_image_path=None,
        preview_thumbnail_paths=[],
        visual_assets_generated=False,
    )

    api_assertions.assert_error(
        api_client.get(f"/api/v1/local-resources/{resource.id}/cover"),
        status_code=404,
        code="VIDEO_ARTWORK_NOT_FOUND",
    )
    api_assertions.assert_error(
        api_client.get(f"/api/v1/local-resources/{resource.id}/previews/0"),
        status_code=404,
        code="PREVIEW_THUMBNAIL_NOT_FOUND",
    )
