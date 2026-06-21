from datetime import datetime, timedelta

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


def test_continue_watching_returns_only_started_unfinished_media(
    api_client: TestClient,
    model_factory,
):
    now = datetime.now()
    unfinished_media = model_factory.media(
        title="Unfinished",
        release_year=2025,
        poster_url="https://example.com/unfinished.jpg",
    )
    unfinished_resource = model_factory.local_resource(media=unfinished_media)
    model_factory.watch_history(
        media=unfinished_media,
        resource=unfinished_resource,
        position_seconds=30,
        duration_seconds=100,
        watched_at=now,
    )
    unknown_duration_media = model_factory.media(title="Unknown duration")
    model_factory.watch_history(
        media=unknown_duration_media,
        position_seconds=15,
        duration_seconds=None,
        watched_at=now - timedelta(minutes=1),
    )
    completed_media = model_factory.media(title="Completed")
    model_factory.watch_history(
        media=completed_media,
        position_seconds=100,
        duration_seconds=100,
        watched_at=now + timedelta(minutes=1),
    )
    not_started_media = model_factory.media(title="Not started")
    model_factory.watch_history(
        media=not_started_media,
        position_seconds=0,
        duration_seconds=100,
        watched_at=now + timedelta(minutes=2),
    )

    payload = api_client.get("/api/v1/history/continue-watching").json()

    assert payload["total"] == 2
    assert [item["media"]["id"] for item in payload["items"]] == [
        unfinished_media.id,
        unknown_duration_media.id,
    ]
    assert payload["items"][0]["media"] == {
        "id": unfinished_media.id,
        "title": "Unfinished",
        "media_type": "movie",
        "release_year": 2025,
        "poster_url": "https://example.com/unfinished.jpg",
    }


def test_recently_watched_is_paginated_by_watched_time(
    api_client: TestClient,
    model_factory,
):
    now = datetime.now()
    oldest = model_factory.media(title="Oldest")
    newest = model_factory.media(title="Newest")
    middle = model_factory.media(title="Middle")
    model_factory.watch_history(media=oldest, watched_at=now - timedelta(days=2))
    model_factory.watch_history(media=newest, watched_at=now)
    model_factory.watch_history(media=middle, watched_at=now - timedelta(days=1))

    first_page = api_client.get(
        "/api/v1/history/recent",
        params={"page": 1, "page_size": 2},
    ).json()
    second_page = api_client.get(
        "/api/v1/history/recent",
        params={"page": 2, "page_size": 2},
    ).json()

    assert [item["media"]["id"] for item in first_page["items"]] == [
        newest.id,
        middle.id,
    ]
    assert first_page["total"] == 3
    assert first_page["total_pages"] == 2
    assert first_page["has_next"] is True
    assert [item["media"]["id"] for item in second_page["items"]] == [oldest.id]
    assert second_page["has_previous"] is True


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/history/continue-watching",
        "/api/v1/history/recent",
    ],
)
def test_playback_history_lists_validate_pagination(
    api_client: TestClient,
    api_assertions,
    path: str,
):
    api_assertions.assert_validation_error(
        api_client.get(path, params={"page_size": 201}),
        ["query", "page_size"],
    )
