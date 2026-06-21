from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from videocenter.models.media import LocalResource, MediaStatus
from videocenter.models.scan import ScanTask, ScanTaskStatus
from videocenter.services.local_library import restore_scan_tasks, run_scan_task


def test_scan_task_runs_in_background_and_reports_progress(
    api_client: TestClient,
    db_session: Session,
    monkeypatch,
):
    root = Path("data/media/scan-progress").resolve()
    root.mkdir(parents=True, exist_ok=True)
    (root / "first.mp4").write_bytes(b"first")
    (root / "second.mkv").write_bytes(b"second")
    started: list[int] = []
    monkeypatch.setattr(
        "videocenter.api.routes.local_resources.start_scan_task",
        started.append,
    )

    try:
        response = api_client.post(
            "/api/v1/local-resources/scan",
            json={"path": str(root), "incremental": True},
        )
        assert response.status_code == 202
        task = response.json()
        assert task["status"] == "waiting"
        assert task["progress"] == 0
        assert started == [task["id"]]

        run_scan_task(task["id"])
        detail = api_client.get(f"/api/v1/local-resources/scan-tasks/{task['id']}").json()
        assert detail["status"] == "completed"
        assert detail["progress"] == 100
        assert detail["total_files"] == 2
        assert detail["processed_files"] == 2
        assert detail["discovered_files"] == 2
        assert detail["added_files"] == 2
        assert detail["updated_files"] == 0
        assert detail["skipped_files"] == 0
        assert len(api_client.get("/api/v1/local-resources").json()) == 2
        assert api_client.get("/api/v1/local-resources/scan-tasks").json()[0]["id"] == task["id"]
    finally:
        for path in root.iterdir():
            path.unlink()
        root.rmdir()


def test_incremental_scan_skips_unchanged_and_updates_changed_files(
    api_client: TestClient,
    db_session: Session,
    monkeypatch,
):
    root = Path("data/media/scan-incremental").resolve()
    root.mkdir(parents=True, exist_ok=True)
    video = root / "movie.mp4"
    video.write_bytes(b"version-one")
    monkeypatch.setattr(
        "videocenter.api.routes.local_resources.start_scan_task",
        lambda task_id: None,
    )

    try:
        first_id = api_client.post(
            "/api/v1/local-resources/scan",
            json={"path": str(root)},
        ).json()["id"]
        run_scan_task(first_id)

        second_id = api_client.post(
            "/api/v1/local-resources/scan",
            json={"path": str(root), "incremental": True},
        ).json()["id"]
        run_scan_task(second_id)
        second = api_client.get(f"/api/v1/local-resources/scan-tasks/{second_id}").json()
        assert second["skipped_files"] == 1
        assert second["updated_files"] == 0

        video.write_bytes(b"version-two-is-different")
        third_id = api_client.post(
            "/api/v1/local-resources/scan",
            json={"path": str(root), "incremental": True},
        ).json()["id"]
        run_scan_task(third_id)
        third = api_client.get(f"/api/v1/local-resources/scan-tasks/{third_id}").json()
        assert third["updated_files"] == 1
        assert third["skipped_files"] == 0

        resource = db_session.query(LocalResource).one()
        assert resource.file_size == video.stat().st_size
        assert resource.modified_at_ns == video.stat().st_mtime_ns
    finally:
        video.unlink(missing_ok=True)
        root.rmdir()


def test_scan_detects_deleted_and_restored_video_files(
    api_client: TestClient,
    db_session: Session,
    model_factory,
    monkeypatch,
):
    root = Path("data/media/scan-deleted").resolve()
    root.mkdir(parents=True, exist_ok=True)
    video = root / "movie.mp4"
    video.write_bytes(b"video")
    media = model_factory.media(status=MediaStatus.PENDING)
    monkeypatch.setattr(
        "videocenter.api.routes.local_resources.start_scan_task",
        lambda task_id: None,
    )

    try:
        first_id = api_client.post(
            "/api/v1/local-resources/scan",
            json={"path": str(root), "media_id": media.id},
        ).json()["id"]
        run_scan_task(first_id)
        first = api_client.get(f"/api/v1/local-resources/scan-tasks/{first_id}").json()
        assert first["added_files"] == 1
        assert first["missing_files"] == 0
        db_session.refresh(media)
        assert media.status == MediaStatus.AVAILABLE

        video.unlink()
        missing_id = api_client.post(
            "/api/v1/local-resources/scan",
            json={"path": str(root)},
        ).json()["id"]
        run_scan_task(missing_id)
        missing = api_client.get(f"/api/v1/local-resources/scan-tasks/{missing_id}").json()
        assert missing["discovered_files"] == 0
        assert missing["missing_files"] == 1
        resource = db_session.query(LocalResource).one()
        db_session.refresh(resource)
        db_session.refresh(media)
        assert resource.is_available is False
        assert resource.missing_at is not None
        assert media.status == MediaStatus.MISSING

        video.write_bytes(b"video-restored")
        restored_id = api_client.post(
            "/api/v1/local-resources/scan",
            json={"path": str(root), "incremental": True},
        ).json()["id"]
        run_scan_task(restored_id)
        restored = api_client.get(f"/api/v1/local-resources/scan-tasks/{restored_id}").json()
        assert restored["restored_files"] == 1
        assert restored["added_files"] == 0
        db_session.refresh(resource)
        db_session.refresh(media)
        assert resource.is_available is True
        assert resource.missing_at is None
        assert media.status == MediaStatus.AVAILABLE
    finally:
        video.unlink(missing_ok=True)
        root.rmdir()


def test_scan_only_marks_resources_inside_requested_directory_missing(
    api_client: TestClient,
    db_session: Session,
    model_factory,
    monkeypatch,
):
    root = Path("data/media/scan-scope").resolve()
    first = root / "first"
    second = root / "second"
    first.mkdir(parents=True, exist_ok=True)
    second.mkdir(parents=True, exist_ok=True)
    outside_file = second / "outside.mp4"
    outside_file.write_bytes(b"outside")
    resource = model_factory.local_resource(
        file_path=str(outside_file.resolve()),
        file_name=outside_file.name,
        modified_at_ns=outside_file.stat().st_mtime_ns,
    )
    monkeypatch.setattr(
        "videocenter.api.routes.local_resources.start_scan_task",
        lambda task_id: None,
    )

    try:
        task_id = api_client.post(
            "/api/v1/local-resources/scan",
            json={"path": str(first)},
        ).json()["id"]
        run_scan_task(task_id)

        db_session.refresh(resource)
        assert resource.is_available is True
        assert (
            api_client.get(f"/api/v1/local-resources/scan-tasks/{task_id}").json()["missing_files"]
            == 0
        )
    finally:
        outside_file.unlink()
        second.rmdir()
        first.rmdir()
        root.rmdir()


def test_scan_task_not_found(api_client: TestClient, api_assertions):
    api_assertions.assert_error(
        api_client.get("/api/v1/local-resources/scan-tasks/999999"),
        status_code=404,
        code="SCAN_TASK_NOT_FOUND",
    )


def test_restore_scan_tasks_requeues_waiting_and_running(
    db_session: Session,
    monkeypatch,
):
    root = str(Path("data/media").resolve())
    first = ScanTask(
        path=root,
        status=ScanTaskStatus.WAITING,
        incremental=True,
    )
    second = ScanTask(
        path=root,
        status=ScanTaskStatus.RUNNING,
        incremental=False,
        progress=50,
        processed_files=5,
    )
    completed = ScanTask(
        path=root,
        status=ScanTaskStatus.COMPLETED,
        incremental=True,
        progress=100,
    )
    db_session.add_all([first, second, completed])
    db_session.commit()
    started: list[int] = []
    monkeypatch.setattr(
        "videocenter.services.local_library.start_scan_task",
        started.append,
    )

    restored = restore_scan_tasks()

    assert restored == 2
    assert started == [first.id, second.id]
    db_session.expire_all()
    recovered = db_session.get(ScanTask, second.id)
    assert recovered.status == ScanTaskStatus.WAITING
    assert recovered.progress == 0
    assert recovered.processed_files == 0
    assert db_session.get(ScanTask, completed.id).status == ScanTaskStatus.COMPLETED
