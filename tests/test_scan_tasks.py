from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from videocenter.models.background_task import (
    BackgroundTask,
    BackgroundTaskStatus,
    BackgroundTaskType,
)
from videocenter.models.media import LocalResource, MediaStatus
from videocenter.models.scan import ScanTask, ScanTaskStatus
from videocenter.services.local_library import restore_scan_tasks, run_scan_task
from videocenter.services.media_artwork import GeneratedVideoArtwork
from videocenter.services.media_probe import (
    AudioTrackInfo,
    SubtitleTrackInfo,
    VideoMediaInfo,
)


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
        background = db_session.scalar(
            select(BackgroundTask).where(
                BackgroundTask.task_type == BackgroundTaskType.MEDIA_SCAN,
                BackgroundTask.source_task_id == task["id"],
            )
        )
        assert background is not None
        assert background.status == BackgroundTaskStatus.WAITING

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
        db_session.refresh(background)
        assert background.status == BackgroundTaskStatus.COMPLETED
        assert background.progress == 100
        assert background.processed_items == 2
        assert background.total_items == 2
        assert background.task_result["added_files"] == 2
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


def test_scan_recognizes_movie_and_series_file_names(
    api_client: TestClient,
    db_session: Session,
    monkeypatch,
):
    root = Path("data/media/scan-filenames").resolve()
    root.mkdir(parents=True, exist_ok=True)
    movie = root / "The.Matrix.1999.1080p.BluRay.mkv"
    episode = root / "The.Show.S02E07.720p.WEB-DL.mp4"
    movie.write_bytes(b"movie")
    episode.write_bytes(b"episode")
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

        resources = {
            item["file_name"]: item for item in api_client.get("/api/v1/local-resources").json()
        }
        movie_resource = resources[movie.name]
        assert movie_resource["detected_media_type"] == "movie"
        assert movie_resource["parsed_title"] == "The Matrix"
        assert movie_resource["parsed_release_year"] == 1999

        episode_resource = resources[episode.name]
        assert episode_resource["detected_media_type"] == "series"
        assert episode_resource["parsed_title"] == "The Show"
        assert episode_resource["parsed_season_number"] == 2
        assert episode_resource["parsed_episode_number"] == 7
    finally:
        movie.unlink(missing_ok=True)
        episode.unlink(missing_ok=True)
        root.rmdir()


def test_scan_probes_video_media_information(
    api_client: TestClient,
    db_session: Session,
    monkeypatch,
):
    root = Path("data/media/scan-media-info").resolve()
    root.mkdir(parents=True, exist_ok=True)
    video = root / "movie.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(
        "videocenter.api.routes.local_resources.start_scan_task",
        lambda task_id: None,
    )
    monkeypatch.setattr(
        "videocenter.services.local_resource_analysis.probe_video_file",
        lambda path: VideoMediaInfo(
            duration_seconds=125.5,
            width=1920,
            height=1080,
            video_codec="h264",
            bitrate=8_000_000,
            audio_codec="aac",
            audio_tracks=(
                AudioTrackInfo(
                    stream_index=1,
                    codec="aac",
                    language="chi",
                    title="中文",
                    channels=2,
                    channel_layout="stereo",
                    is_default=True,
                ),
            ),
            subtitle_tracks=(
                SubtitleTrackInfo(
                    stream_index=2,
                    codec="ass",
                    language="chi",
                    title="简体中文",
                    is_default=True,
                    is_forced=False,
                ),
            ),
        ),
    )
    cover = root / "generated-cover.jpg"
    preview = root / "generated-preview.jpg"
    monkeypatch.setattr(
        "videocenter.services.local_resource_analysis.generate_video_artwork",
        lambda path, **kwargs: GeneratedVideoArtwork(
            cover_image_path=str(cover),
            preview_thumbnail_paths=(str(preview),),
        ),
    )

    try:
        task_id = api_client.post(
            "/api/v1/local-resources/scan",
            json={"path": str(root)},
        ).json()["id"]
        run_scan_task(task_id)

        resource = api_client.get("/api/v1/local-resources").json()[0]
        assert resource["duration_seconds"] == 125.5
        assert resource["video_width"] == 1920
        assert resource["video_height"] == 1080
        assert resource["video_codec"] == "h264"
        assert resource["bitrate"] == 8_000_000
        assert resource["audio_codec"] == "aac"
        assert resource["audio_tracks"][0]["channels"] == 2
        assert resource["audio_tracks"][0]["channel_layout"] == "stereo"
        assert resource["embedded_subtitles"][0]["codec"] == "ass"
        assert resource["embedded_subtitles"][0]["language"] == "chi"
        assert resource["cover_image_path"] == str(cover)
        assert resource["preview_thumbnail_paths"] == [str(preview)]
        assert resource["visual_assets_generated"] is True
        assert db_session.query(LocalResource).one().media_info_probed is True
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
