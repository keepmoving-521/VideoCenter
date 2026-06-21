import shutil
import subprocess
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

    def fake_run(command, **kwargs):
        del kwargs
        playlist = Path(command[-1])
        segment_pattern = Path(command[command.index("-hls_segment_filename") + 1])
        segment = Path(str(segment_pattern).replace("%05d", "00000"))
        segment.write_bytes(b"segment-data")
        playlist.write_text(
            "#EXTM3U\n#EXT-X-VERSION:6\n#EXTINF:6.0,\nsegments/segment00000.ts\n#EXT-X-ENDLIST\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("videocenter.services.hls.subprocess.run", fake_run)

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
