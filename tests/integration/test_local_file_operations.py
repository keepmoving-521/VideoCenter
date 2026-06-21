from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.support.api import ApiAssertions
from videocenter.models.history import WatchHistory
from videocenter.models.media import LocalResource, MediaStatus
from videocenter.services.local_file_operations import TRASH_DIRECTORY_NAME
from videocenter.services.local_library import run_scan_task

pytestmark = pytest.mark.integration


def test_rename_local_file_updates_resource_metadata(
    api_client: TestClient,
    db_session: Session,
    model_factory,
):
    root = Path("data/media/file-rename").resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = root / "Old.Movie.2020.mp4"
    source.write_bytes(b"movie")
    resource = model_factory.local_resource(
        file_path=str(source),
        file_name=source.name,
        file_size=source.stat().st_size,
    )

    try:
        response = api_client.put(
            f"/api/v1/local-resources/{resource.id}/rename",
            json={"file_name": "New.Movie.2024.1080p.mp4"},
        )

        assert response.status_code == 200
        payload = response.json()
        target = root / "New.Movie.2024.1080p.mp4"
        assert target.is_file()
        assert not source.exists()
        assert payload["file_name"] == target.name
        assert payload["parsed_title"] == "New Movie"
        assert payload["parsed_release_year"] == 2024
        db_session.refresh(resource)
        assert resource.file_path == str(target)
    finally:
        source.unlink(missing_ok=True)
        (root / "New.Movie.2024.1080p.mp4").unlink(missing_ok=True)
        root.rmdir()


def test_rename_rejects_path_and_existing_target(
    api_client: TestClient,
    api_assertions: ApiAssertions,
    model_factory,
):
    root = Path("data/media/file-rename-conflict").resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = root / "source.mp4"
    target = root / "target.mp4"
    source.write_bytes(b"source")
    target.write_bytes(b"target")
    resource = model_factory.local_resource(
        file_path=str(source),
        file_name=source.name,
    )

    try:
        api_assertions.assert_error(
            api_client.put(
                f"/api/v1/local-resources/{resource.id}/rename",
                json={"file_name": "../escape.mp4"},
            ),
            status_code=409,
            code="INVALID_LOCAL_FILE_NAME",
        )
        api_assertions.assert_error(
            api_client.put(
                f"/api/v1/local-resources/{resource.id}/rename",
                json={"file_name": target.name},
            ),
            status_code=409,
            code="LOCAL_FILE_NAME_CONFLICT",
        )
        assert source.is_file()
    finally:
        source.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        root.rmdir()


def test_safe_delete_moves_file_to_trash_and_updates_media_status(
    api_client: TestClient,
    db_session: Session,
    model_factory,
):
    root = Path("data/media/file-delete").resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = root / "movie.mp4"
    source.write_bytes(b"movie")
    media = model_factory.media(status=MediaStatus.AVAILABLE)
    resource = model_factory.local_resource(
        media=media,
        file_path=str(source),
        file_name=source.name,
    )

    response = api_client.delete(f"/api/v1/local-resources/{resource.id}/file")

    assert response.status_code == 200
    assert response.json()["is_available"] is False
    assert not source.exists()
    trash_root = Path("data/media").resolve() / TRASH_DIRECTORY_NAME
    trashed_files = list(trash_root.rglob("*-movie.mp4"))
    assert len(trashed_files) == 1
    assert trashed_files[0].read_bytes() == b"movie"
    db_session.refresh(media)
    assert media.status == MediaStatus.MISSING

    trashed_files[0].unlink()
    trashed_files[0].parent.rmdir()
    trash_root.rmdir()
    root.rmdir()


def test_scan_ignores_files_in_safe_delete_trash(
    api_client: TestClient,
    db_session: Session,
    model_factory,
    monkeypatch,
):
    root = Path("data/media/file-delete-scan").resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = root / "movie.mp4"
    source.write_bytes(b"movie")
    resource = model_factory.local_resource(
        file_path=str(source),
        file_name=source.name,
    )
    monkeypatch.setattr(
        "videocenter.api.routes.local_resources.start_scan_task",
        lambda task_id: None,
    )

    api_client.delete(f"/api/v1/local-resources/{resource.id}/file")
    task_id = api_client.post(
        "/api/v1/local-resources/scan",
        json={"path": str(Path("data/media").resolve())},
    ).json()["id"]
    run_scan_task(task_id)

    assert db_session.query(LocalResource).count() == 1
    detail = api_client.get(f"/api/v1/local-resources/scan-tasks/{task_id}").json()
    assert detail["discovered_files"] == 0

    trash_root = Path("data/media").resolve() / TRASH_DIRECTORY_NAME
    trashed_file = next(trash_root.rglob("*-movie.mp4"))
    trashed_file.unlink()
    trashed_file.parent.rmdir()
    trash_root.rmdir()
    root.rmdir()


def test_cleanup_invalid_resources_preserves_existing_and_detaches_history(
    api_client: TestClient,
    db_session: Session,
    model_factory,
):
    media = model_factory.media(status=MediaStatus.MISSING)
    invalid = model_factory.local_resource(
        media=media,
        is_available=False,
        file_path=str(Path("data/media/missing-cleanup.mp4").resolve()),
    )
    existing_path = Path("data/media/existing-cleanup.mp4").resolve()
    existing_path.write_bytes(b"existing")
    existing = model_factory.local_resource(
        is_available=False,
        file_path=str(existing_path),
        file_name=existing_path.name,
    )
    history = model_factory.watch_history(media=media, resource=invalid)
    invalid_id = invalid.id

    try:
        response = api_client.post("/api/v1/local-resources/cleanup-invalid")

        assert response.status_code == 200
        assert response.json() == {
            "deleted_count": 1,
            "deleted_resource_ids": [invalid_id],
        }
        db_session.expire_all()
        assert db_session.get(LocalResource, invalid_id) is None
        assert db_session.get(LocalResource, existing.id) is not None
        assert db_session.get(WatchHistory, history.id).resource_id is None
        assert db_session.get(type(media), media.id).status == MediaStatus.PENDING
    finally:
        existing_path.unlink(missing_ok=True)
