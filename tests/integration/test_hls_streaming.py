import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from videocenter.models.hls import HlsTask
from videocenter.services.hls import run_hls_task

pytestmark = pytest.mark.integration


def test_hls_task_generates_playlist_and_serves_segments(
    api_client: TestClient,
    db_session: Session,
    model_factory,
    monkeypatch,
):
    video = Path("data/media/hls-source.mkv").resolve()
    video.write_bytes(b"video")
    resource = model_factory.local_resource(
        file_path=str(video),
        file_name=video.name,
        checksum_sha256="a" * 64,
    )
    monkeypatch.setattr(
        "videocenter.api.routes.streaming.start_hls_task",
        lambda task_id: None,
    )
    monkeypatch.setattr(
        "videocenter.services.hls._ffmpeg_executable",
        lambda: "ffmpeg",
    )

    class FakeProcess:
        def __init__(self, command, **kwargs):
            del kwargs
            playlist = Path(command[-1])
            segment_pattern = Path(command[command.index("-hls_segment_filename") + 1])
            segment = Path(str(segment_pattern).replace("%05d", "00000"))
            segment.write_bytes(b"segment-data")
            playlist.write_text(
                "#EXTM3U\n#EXT-X-VERSION:6\n"
                "#EXTINF:6.0,\nsegments/segment00000.ts\n#EXT-X-ENDLIST\n",
                encoding="utf-8",
            )
            self.stdout = iter(["out_time_us=3000000\n", "out_time_us=6000000\n"])
            from io import StringIO

            self.stderr = StringIO("")

        def wait(self, timeout=None):
            del timeout
            return 0

    def fake_popen(command, **kwargs):
        return FakeProcess(command, **kwargs)

    monkeypatch.setattr("videocenter.services.hls.subprocess.Popen", fake_popen)

    try:
        response = api_client.post(f"/api/v1/stream/{resource.id}/hls")
        assert response.status_code == 202
        created = response.json()
        assert created["status"] == "waiting"
        assert created["playlist_url"] is None

        run_hls_task(created["id"])
        detail = api_client.get(f"/api/v1/stream/hls-tasks/{created['id']}").json()
        assert detail["status"] == "completed"
        assert detail["progress"] == 100
        assert detail["cache_available"] is True
        assert detail["playlist_url"] == (f"/api/v1/stream/hls/{created['id']}/index.m3u8")

        playlist = api_client.get(detail["playlist_url"])
        assert playlist.status_code == 200
        assert playlist.headers["content-type"].startswith("application/vnd.apple.mpegurl")
        assert "segments/segment00000.ts" in playlist.text

        segment = api_client.get(f"/api/v1/stream/hls/{created['id']}/segments/segment00000.ts")
        assert segment.status_code == 200
        assert segment.headers["content-type"].startswith("video/mp2t")
        assert segment.content == b"segment-data"

        reused = api_client.post(f"/api/v1/stream/{resource.id}/hls").json()
        assert reused["id"] == created["id"]
        assert db_session.query(HlsTask).count() == 1
    finally:
        video.unlink(missing_ok=True)
        shutil.rmtree(
            Path("data/media/.videocenter-cache/hls").resolve(),
            ignore_errors=True,
        )


def test_hls_playlist_requires_completed_task(
    api_client: TestClient,
    model_factory,
):
    resource = model_factory.local_resource()
    task = HlsTask(resource_id=resource.id)
    from videocenter.core.database import SessionLocal

    with SessionLocal() as db:
        db.add(task)
        db.commit()
        task_id = task.id

    response = api_client.get(f"/api/v1/stream/hls/{task_id}/index.m3u8")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "HLS_NOT_READY"


def test_hls_cache_cleanup_removes_only_expired_finished_tasks(
    api_client: TestClient,
    db_session: Session,
    model_factory,
):
    from datetime import datetime, timedelta

    from videocenter.models.hls import HlsTaskStatus

    resource = model_factory.local_resource()
    old_directory = Path("data/media/.videocenter-cache/hls/old-task").resolve()
    active_directory = Path("data/media/.videocenter-cache/hls/active-task").resolve()
    old_directory.mkdir(parents=True, exist_ok=True)
    active_directory.mkdir(parents=True, exist_ok=True)
    (old_directory / "index.m3u8").write_bytes(b"playlist")
    (old_directory / "segment.ts").write_bytes(b"segment")
    (active_directory / "index.m3u8").write_bytes(b"active")
    old = HlsTask(
        resource_id=resource.id,
        status=HlsTaskStatus.COMPLETED,
        progress=100,
        output_directory=str(old_directory),
        playlist_path=str(old_directory / "index.m3u8"),
        completed_at=datetime.now() - timedelta(hours=48),
    )
    active = HlsTask(
        resource_id=resource.id,
        status=HlsTaskStatus.RUNNING,
        progress=50,
        output_directory=str(active_directory),
        playlist_path=str(active_directory / "index.m3u8"),
    )
    db_session.add_all([old, active])
    db_session.commit()

    try:
        response = api_client.post(
            "/api/v1/stream/hls/cache/cleanup",
            json={"max_age_hours": 24},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["cleaned_task_ids"] == [old.id]
        assert payload["cleaned_task_count"] == 1
        assert payload["removed_directory_count"] == 1
        assert payload["reclaimed_bytes"] == len(b"playlistsegment")
        assert not old_directory.exists()
        assert active_directory.exists()
        db_session.refresh(old)
        assert old.output_directory is None
        assert old.playlist_path is None
        detail = api_client.get(f"/api/v1/stream/hls-tasks/{old.id}").json()
        assert detail["cache_available"] is False
        assert detail["playlist_url"] is None
    finally:
        shutil.rmtree(old_directory, ignore_errors=True)
        shutil.rmtree(active_directory, ignore_errors=True)
