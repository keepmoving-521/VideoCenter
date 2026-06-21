from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.support.api import ApiAssertions

pytestmark = pytest.mark.integration


def test_media_directory_create_list_and_update(
    api_client: TestClient,
    api_assertions: ApiAssertions,
):
    media_root = Path("data/media").resolve()
    first_path = media_root / "library-one"
    second_path = media_root / "library-two"
    first_path.mkdir(parents=True, exist_ok=True)
    second_path.mkdir(parents=True, exist_ok=True)

    try:
        first = api_assertions.assert_status(
            api_client.post(
                "/api/v1/media-directories",
                json={
                    "name": "Primary Library",
                    "path": "library-one",
                },
            ),
            201,
        )
        assert first["path"] == str(first_path)
        assert first["is_default"] is True
        assert first["is_enabled"] is True
        assert first["auto_scan"] is True

        second = api_assertions.assert_status(
            api_client.post(
                "/api/v1/media-directories",
                json={
                    "name": "Secondary Library",
                    "path": str(second_path),
                    "is_default": True,
                    "auto_scan": False,
                },
            ),
            201,
        )
        assert second["is_default"] is True

        directories = api_client.get("/api/v1/media-directories").json()
        assert [item["id"] for item in directories] == [second["id"], first["id"]]
        assert directories[1]["is_default"] is False

        updated = api_assertions.assert_status(
            api_client.patch(
                f"/api/v1/media-directories/{first['id']}",
                json={
                    "name": "Archive Library",
                    "is_enabled": False,
                    "auto_scan": False,
                },
            ),
            200,
        )
        assert updated["name"] == "Archive Library"
        assert updated["is_enabled"] is False
        assert updated["auto_scan"] is False
    finally:
        second_path.rmdir()
        first_path.rmdir()


def test_media_directory_rejects_duplicates_and_unsafe_paths(
    api_client: TestClient,
    api_assertions: ApiAssertions,
):
    media_root = Path("data/media").resolve()
    directory_path = media_root / "duplicate-library"
    directory_path.mkdir(parents=True, exist_ok=True)

    try:
        created = api_client.post(
            "/api/v1/media-directories",
            json={"name": "Duplicate Library", "path": str(directory_path)},
        ).json()

        api_assertions.assert_error(
            api_client.post(
                "/api/v1/media-directories",
                json={"name": "Duplicate Library", "path": str(media_root)},
            ),
            status_code=409,
            code="MEDIA_DIRECTORY_NAME_EXISTS",
        )
        api_assertions.assert_error(
            api_client.post(
                "/api/v1/media-directories",
                json={"name": "Another Library", "path": str(directory_path)},
            ),
            status_code=409,
            code="MEDIA_DIRECTORY_PATH_EXISTS",
        )
        api_assertions.assert_error(
            api_client.post(
                "/api/v1/media-directories",
                json={"name": "Unsafe", "path": "../outside"},
            ),
            status_code=400,
            code="INVALID_MEDIA_DIRECTORY_PATH",
        )
        api_assertions.assert_error(
            api_client.patch(
                f"/api/v1/media-directories/{created['id']}",
                json={"is_default": False},
            ),
            status_code=409,
            code="MEDIA_DIRECTORY_DEFAULT_REQUIRED",
        )
    finally:
        directory_path.rmdir()


def test_media_directory_not_found(
    api_client: TestClient,
    api_assertions: ApiAssertions,
):
    api_assertions.assert_error(
        api_client.patch(
            "/api/v1/media-directories/999999",
            json={"name": "Missing"},
        ),
        status_code=404,
        code="MEDIA_DIRECTORY_NOT_FOUND",
    )
