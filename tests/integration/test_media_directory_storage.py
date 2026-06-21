from collections import namedtuple
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.support.api import ApiAssertions

pytestmark = pytest.mark.integration
DiskUsage = namedtuple("DiskUsage", ["total", "used", "free"])


def test_media_directory_storage_statistics_and_warning(
    api_client: TestClient,
    model_factory,
    monkeypatch,
):
    root = Path("data/media/storage-stats").resolve()
    root.mkdir(parents=True, exist_ok=True)
    directory = model_factory.media_directory(
        name="Storage Stats",
        path=str(root),
        capacity_warning_enabled=True,
        capacity_warning_threshold_percent=80,
    )
    inside = root / "inside.mp4"
    outside = Path("data/media/outside.mp4").resolve()
    model_factory.local_resource(
        file_path=str(inside),
        file_name=inside.name,
        file_size=300,
    )
    model_factory.local_resource(
        file_path=str(outside),
        file_name=outside.name,
        file_size=500,
    )
    model_factory.local_resource(
        file_path=str(root / "missing.mp4"),
        file_name="missing.mp4",
        file_size=700,
        is_available=False,
    )
    monkeypatch.setattr(
        "videocenter.services.media_storage.shutil.disk_usage",
        lambda path: DiskUsage(total=1_000, used=850, free=150),
    )

    try:
        response = api_client.get(f"/api/v1/media-directories/{directory.id}/storage")

        assert response.status_code == 200
        assert response.json() == {
            "directory_id": directory.id,
            "name": "Storage Stats",
            "path": str(root),
            "total_bytes": 1_000,
            "used_bytes": 850,
            "free_bytes": 150,
            "usage_percent": 85.0,
            "managed_file_count": 1,
            "managed_file_bytes": 300,
            "warning_enabled": True,
            "warning_threshold_percent": 80,
            "warning_triggered": True,
        }
        listed = api_client.get("/api/v1/media-directories/storage").json()
        assert listed == [response.json()]
    finally:
        root.rmdir()


def test_capacity_warning_can_be_configured_and_disabled(
    api_client: TestClient,
    monkeypatch,
):
    root = Path("data/media/storage-warning-config").resolve()
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "videocenter.services.media_storage.shutil.disk_usage",
        lambda path: DiskUsage(total=100, used=99, free=1),
    )

    try:
        created = api_client.post(
            "/api/v1/media-directories",
            json={
                "name": "Warning Config",
                "path": str(root),
                "capacity_warning_enabled": False,
                "capacity_warning_threshold_percent": 75,
            },
        ).json()
        assert created["capacity_warning_enabled"] is False
        assert created["capacity_warning_threshold_percent"] == 75
        stats = api_client.get(f"/api/v1/media-directories/{created['id']}/storage").json()
        assert stats["usage_percent"] == 99.0
        assert stats["warning_triggered"] is False

        updated = api_client.patch(
            f"/api/v1/media-directories/{created['id']}",
            json={
                "capacity_warning_enabled": True,
                "capacity_warning_threshold_percent": 95,
            },
        ).json()
        assert updated["capacity_warning_enabled"] is True
        assert updated["capacity_warning_threshold_percent"] == 95
        assert (
            api_client.get(f"/api/v1/media-directories/{created['id']}/storage").json()[
                "warning_triggered"
            ]
            is True
        )
    finally:
        root.rmdir()


@pytest.mark.parametrize("threshold", [0, 101])
def test_capacity_warning_threshold_validation(
    api_client: TestClient,
    api_assertions: ApiAssertions,
    threshold: int,
):
    details = api_assertions.assert_error(
        api_client.post(
            "/api/v1/media-directories",
            json={
                "name": "Invalid threshold",
                "path": str(Path("data/media").resolve()),
                "capacity_warning_threshold_percent": threshold,
            },
        ),
        status_code=422,
        code="VALIDATION_ERROR",
    )["error"]["details"]
    assert any(
        item["loc"][:2] == ["body", "capacity_warning_threshold_percent"] for item in details
    )


def test_storage_directory_not_found(
    api_client: TestClient,
    api_assertions: ApiAssertions,
):
    api_assertions.assert_error(
        api_client.get("/api/v1/media-directories/999999/storage"),
        status_code=404,
        code="MEDIA_DIRECTORY_NOT_FOUND",
    )
