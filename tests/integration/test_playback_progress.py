import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from videocenter.models.history import WatchHistory

pytestmark = pytest.mark.integration


def test_save_playback_progress_creates_and_updates_single_history(
    api_client: TestClient,
    db_session: Session,
    model_factory,
):
    media = model_factory.media()
    resource = model_factory.local_resource(media=media, duration_seconds=120)

    created = api_client.put(
        f"/api/v1/stream/{resource.id}/progress",
        json={"position_seconds": 30},
    )

    assert created.status_code == 200
    assert created.json()["media_id"] == media.id
    assert created.json()["resource_id"] == resource.id
    assert created.json()["position_seconds"] == 30
    assert created.json()["duration_seconds"] == 120

    updated = api_client.put(
        f"/api/v1/stream/{resource.id}/progress",
        json={"position_seconds": 75, "duration_seconds": 125},
    )

    assert updated.status_code == 200
    assert updated.json()["id"] == created.json()["id"]
    assert updated.json()["position_seconds"] == 75
    assert updated.json()["duration_seconds"] == 125
    history_count = db_session.scalar(select(func.count()).select_from(WatchHistory))
    assert history_count == 1


def test_save_playback_progress_requires_associated_resource(
    api_client: TestClient,
    api_assertions,
    model_factory,
):
    resource = model_factory.local_resource()

    api_assertions.assert_error(
        api_client.put(
            f"/api/v1/stream/{resource.id}/progress",
            json={"position_seconds": 10},
        ),
        status_code=409,
        code="RESOURCE_NOT_ASSOCIATED",
    )


def test_save_playback_progress_rejects_position_beyond_probed_duration(
    api_client: TestClient,
    api_assertions,
    model_factory,
):
    media = model_factory.media()
    resource = model_factory.local_resource(media=media, duration_seconds=100)

    api_assertions.assert_error(
        api_client.put(
            f"/api/v1/stream/{resource.id}/progress",
            json={"position_seconds": 101},
        ),
        status_code=422,
        code="PLAYBACK_POSITION_EXCEEDS_DURATION",
    )


def test_save_playback_progress_returns_not_found_for_unknown_resource(
    api_client: TestClient,
    api_assertions,
):
    api_assertions.assert_error(
        api_client.put(
            "/api/v1/stream/999999/progress",
            json={"position_seconds": 10},
        ),
        status_code=404,
        code="LOCAL_RESOURCE_NOT_FOUND",
    )


def test_get_single_media_playback_progress(
    api_client: TestClient,
    model_factory,
):
    media = model_factory.media()
    resource = model_factory.local_resource(media=media)
    history = model_factory.watch_history(
        media=media,
        resource=resource,
        position_seconds=48.5,
        duration_seconds=120,
    )

    response = api_client.get(f"/api/v1/history/{media.id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": history.id,
        "media_id": media.id,
        "resource_id": resource.id,
        "position_seconds": 48.5,
        "duration_seconds": 120,
        "watched_at": history.watched_at.isoformat(),
    }


def test_get_playback_progress_distinguishes_missing_history(
    api_client: TestClient,
    api_assertions,
    model_factory,
):
    media = model_factory.media()

    api_assertions.assert_error(
        api_client.get(f"/api/v1/history/{media.id}"),
        status_code=404,
        code="WATCH_HISTORY_NOT_FOUND",
    )


def test_get_playback_progress_returns_not_found_for_unknown_media(
    api_client: TestClient,
    api_assertions,
):
    api_assertions.assert_error(
        api_client.get("/api/v1/history/999999"),
        status_code=404,
        code="MEDIA_NOT_FOUND",
    )
