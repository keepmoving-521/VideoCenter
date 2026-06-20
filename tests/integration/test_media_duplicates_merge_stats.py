from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.support.api import ApiAssertions
from videocenter.models.download import DownloadTask
from videocenter.models.history import WatchHistory
from videocenter.models.media import LocalResource, Media, MediaStatus, MediaType

pytestmark = pytest.mark.integration


def test_duplicate_detection_uses_source_url_and_normalized_title(
    api_client: TestClient,
    model_factory,
):
    first = model_factory.media(
        title="The Matrix",
        release_year=1999,
        source_page_url="https://example.com/matrix/",
    )
    second = model_factory.media(
        title="Different imported title",
        source_page_url="https://example.com/matrix",
    )
    third = model_factory.media(
        title="THE-MATRIX",
        release_year=1999,
        media_type=MediaType.MOVIE,
    )
    model_factory.media(
        title="The Matrix",
        release_year=2003,
        media_type=MediaType.MOVIE,
    )

    response = api_client.get("/api/v1/media/duplicates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["group_count"] == 1
    assert payload["duplicate_media_count"] == 3
    assert payload["groups"][0]["reasons"] == [
        "source_page_url",
        "title_year_type",
    ]
    assert [item["id"] for item in payload["groups"][0]["items"]] == [
        first.id,
        second.id,
        third.id,
    ]


def test_merge_moves_relations_and_keeps_latest_history(
    api_client: TestClient,
    db_session: Session,
    model_factory,
):
    target = model_factory.media(
        title="Merged Series",
        release_year=2024,
        media_type=MediaType.SERIES,
        description=None,
    )
    source = model_factory.media(
        title="MERGED-SERIES",
        release_year=2024,
        media_type=MediaType.SERIES,
        description="Description from source",
        is_favorite=True,
    )
    target_tag = model_factory.tag(name="Drama")
    source_tag = model_factory.tag(name="Mystery")
    target.tags.append(target_tag)
    source.tags.extend([target_tag, source_tag])
    db_session.commit()

    resource = model_factory.local_resource(media=source)
    download = model_factory.download_task(media=source)
    model_factory.watch_history(
        media=target,
        watched_at=datetime.now() - timedelta(days=1),
    )
    new_history = model_factory.watch_history(
        media=source,
        resource=resource,
        position_seconds=80,
        watched_at=datetime.now(),
    )
    expected_position = new_history.position_seconds
    target_season = model_factory.season(media=target, season_number=1)
    model_factory.episode(season=target_season, episode_number=1)
    source_season = model_factory.season(media=source, season_number=1)
    model_factory.episode(season=source_season, episode_number=2)
    second_season = model_factory.season(media=source, season_number=2)
    model_factory.episode(season=second_season, episode_number=1)
    target_id = target.id
    source_id = source.id

    response = api_client.post(
        "/api/v1/media/merge",
        json={
            "target_media_id": target_id,
            "source_media_ids": [source_id],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "target_media_id": target_id,
        "merged_media_ids": [source_id],
        "moved_local_resources": 1,
        "moved_download_tasks": 1,
        "merged_tags": 1,
        "merged_seasons": 2,
        "merged_episodes": 2,
        "merged_watch_history": True,
    }

    detail = api_client.get(f"/api/v1/media/{target_id}").json()
    assert detail["description"] == "Description from source"
    assert detail["is_favorite"] is True
    assert [tag["name"] for tag in detail["tags"]] == ["Drama", "Mystery"]
    assert [season["season_number"] for season in detail["seasons"]] == [1, 2]
    assert [episode["episode_number"] for episode in detail["seasons"][0]["episodes"]] == [
        1,
        2,
    ]

    db_session.expire_all()
    assert db_session.get(Media, source_id) is None
    assert db_session.get(LocalResource, resource.id).media_id == target_id
    assert db_session.get(DownloadTask, download.id).media_id == target_id
    history = db_session.scalar(select(WatchHistory).where(WatchHistory.media_id == target_id))
    assert history is not None
    assert history.position_seconds == expected_position


def test_merge_rejects_non_duplicate_and_missing_media(
    api_client: TestClient,
    api_assertions: ApiAssertions,
    model_factory,
):
    target = model_factory.media(title="One", release_year=2020)
    unrelated = model_factory.media(title="Two", release_year=2021)

    api_assertions.assert_error(
        api_client.post(
            "/api/v1/media/merge",
            json={
                "target_media_id": target.id,
                "source_media_ids": [unrelated.id],
            },
        ),
        status_code=409,
        code="MEDIA_NOT_DUPLICATE",
    )
    error = api_assertions.assert_error(
        api_client.post(
            "/api/v1/media/merge",
            json={
                "target_media_id": target.id,
                "source_media_ids": [999999],
            },
        ),
        status_code=404,
        code="MEDIA_NOT_FOUND",
    )
    assert error["error"]["details"]["missing_ids"] == [999999]


def test_media_library_statistics(
    api_client: TestClient,
    model_factory,
):
    movie = model_factory.media(
        media_type=MediaType.MOVIE,
        status=MediaStatus.AVAILABLE,
        is_favorite=True,
    )
    series = model_factory.media(
        media_type=MediaType.SERIES,
        status=MediaStatus.PENDING,
    )
    model_factory.local_resource(media=movie)
    model_factory.local_resource(media=movie)
    model_factory.download_task(media=series)
    model_factory.tag(name="Statistics")
    season = model_factory.season(media=series)
    model_factory.episode(season=season)

    response = api_client.get("/api/v1/media/stats")

    assert response.status_code == 200
    assert response.json() == {
        "total_media": 2,
        "favorite_media": 1,
        "media_with_local_resources": 1,
        "total_local_resources": 2,
        "total_download_tasks": 1,
        "total_tags": 1,
        "total_seasons": 1,
        "total_episodes": 1,
        "by_type": {"movie": 1, "series": 1},
        "by_status": {"available": 1, "pending": 1},
    }
