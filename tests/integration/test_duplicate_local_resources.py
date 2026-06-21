import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from videocenter.models.media import LocalResource
from videocenter.services.local_library import run_scan_task

pytestmark = pytest.mark.integration


def test_scan_calculates_hash_and_lists_duplicate_files(
    api_client: TestClient,
    db_session: Session,
    monkeypatch,
):
    root = Path("data/media/hash-duplicates").resolve()
    root.mkdir(parents=True, exist_ok=True)
    content = b"same-video-content"
    first = root / "first.mp4"
    second = root / "second.mkv"
    unique = root / "unique.mp4"
    first.write_bytes(content)
    second.write_bytes(content)
    unique.write_bytes(b"unique-content")
    monkeypatch.setattr(
        "videocenter.api.routes.local_resources.start_scan_task",
        lambda task_id: None,
    )

    try:
        task_id = api_client.post(
            "/api/v1/local-resources/scan",
            json={"path": str(root)},
        ).json()["id"]
        run_scan_task(task_id)

        expected_hash = hashlib.sha256(content).hexdigest()
        resources = db_session.query(LocalResource).all()
        assert {resource.checksum_sha256 for resource in resources} == {
            expected_hash,
            hashlib.sha256(b"unique-content").hexdigest(),
        }

        response = api_client.get("/api/v1/local-resources/duplicates")
        assert response.status_code == 200
        payload = response.json()
        assert payload["group_count"] == 1
        assert payload["duplicate_file_count"] == 2
        assert payload["reclaimable_bytes"] == len(content)
        assert payload["groups"][0]["checksum_sha256"] == expected_hash
        assert {item["file_name"] for item in payload["groups"][0]["resources"]} == {
            first.name,
            second.name,
        }
    finally:
        first.unlink(missing_ok=True)
        second.unlink(missing_ok=True)
        unique.unlink(missing_ok=True)
        root.rmdir()


def test_duplicate_query_ignores_missing_resources(
    api_client: TestClient,
    model_factory,
):
    checksum = "a" * 64
    model_factory.local_resource(checksum_sha256=checksum)
    model_factory.local_resource(checksum_sha256=checksum, is_available=False)

    assert api_client.get("/api/v1/local-resources/duplicates").json() == {
        "group_count": 0,
        "duplicate_file_count": 0,
        "reclaimable_bytes": 0,
        "groups": [],
    }
