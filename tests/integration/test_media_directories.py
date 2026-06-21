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

        detail = api_assertions.assert_status(
            api_client.get(f"/api/v1/media-directories/{second['id']}"),
            200,
        )
        assert detail == second

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

        api_assertions.assert_status(
            api_client.delete(f"/api/v1/media-directories/{second['id']}"),
            204,
        )
        remaining = api_client.get("/api/v1/media-directories").json()
        assert len(remaining) == 1
        assert remaining[0]["id"] == first["id"]
        assert remaining[0]["is_default"] is True
        assert remaining[0]["is_enabled"] is True

        api_assertions.assert_status(
            api_client.delete(f"/api/v1/media-directories/{first['id']}"),
            204,
        )
        assert api_client.get("/api/v1/media-directories").json() == []
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
        api_assertions.assert_error(
            api_client.patch(
                f"/api/v1/media-directories/{created['id']}",
                json={"is_enabled": False},
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
    api_assertions.assert_error(
        api_client.get("/api/v1/media-directories/999999"),
        status_code=404,
        code="MEDIA_DIRECTORY_NOT_FOUND",
    )
    api_assertions.assert_error(
        api_client.delete("/api/v1/media-directories/999999"),
        status_code=404,
        code="MEDIA_DIRECTORY_NOT_FOUND",
    )


def test_multiple_media_directories_are_independent(
    api_client: TestClient,
):
    media_root = Path("data/media").resolve()
    paths = [media_root / f"multi-{index}" for index in range(3)]
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)

    try:
        created = [
            api_client.post(
                "/api/v1/media-directories",
                json={
                    "name": f"Library {index}",
                    "path": str(path),
                    "auto_scan": index != 2,
                },
            ).json()
            for index, path in enumerate(paths)
        ]

        assert len(api_client.get("/api/v1/media-directories").json()) == 3
        assert sum(item["is_default"] for item in created) == 1
        assert [item["auto_scan"] for item in created] == [True, True, False]

        promoted = api_client.patch(
            f"/api/v1/media-directories/{created[2]['id']}",
            json={"is_default": True},
        ).json()
        assert promoted["is_default"] is True
        directories = api_client.get("/api/v1/media-directories").json()
        assert sum(item["is_default"] for item in directories) == 1
        assert directories[0]["id"] == created[2]["id"]
    finally:
        for path in reversed(paths):
            path.rmdir()
