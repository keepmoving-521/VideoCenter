from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from videocenter.models.media import LocalResource
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
