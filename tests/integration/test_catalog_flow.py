import pytest
from fastapi.testclient import TestClient

from tests.support.api import ApiAssertions

pytestmark = pytest.mark.integration


def test_artwork_tags_seasons_and_episodes_flow(
    api_client: TestClient,
    api_assertions: ApiAssertions,
):
    media = api_assertions.assert_status(
        api_client.post(
            "/api/v1/media",
            json={
                "title": "Integration Series",
                "media_type": "series",
                "poster_url": "https://example.com/poster.jpg",
                "background_url": "https://example.com/background.jpg",
            },
        ),
        201,
    )
    assert media["poster_url"] == "https://example.com/poster.jpg"
    assert media["background_url"] == "https://example.com/background.jpg"

    drama = api_assertions.assert_status(
        api_client.post("/api/v1/tags", json={"name": "Drama"}),
        201,
    )
    sci_fi = api_assertions.assert_status(
        api_client.post("/api/v1/tags", json={"name": "Science Fiction"}),
        201,
    )
    api_assertions.assert_error(
        api_client.post("/api/v1/tags", json={"name": "drama"}),
        status_code=409,
        code="TAG_ALREADY_EXISTS",
    )

    tags = api_assertions.assert_status(
        api_client.put(
            f"/api/v1/media/{media['id']}/tags",
            json={"tag_ids": [sci_fi["id"], drama["id"], sci_fi["id"]]},
        ),
        200,
    )
    assert [tag["id"] for tag in tags] == [sci_fi["id"], drama["id"]]
    detail = api_assertions.assert_status(
        api_client.get(f"/api/v1/media/{media['id']}"),
        200,
    )
    assert {tag["name"] for tag in detail["tags"]} == {"Drama", "Science Fiction"}

    season = api_assertions.assert_status(
        api_client.post(
            f"/api/v1/media/{media['id']}/seasons",
            json={
                "season_number": 1,
                "title": "First Season",
                "poster_url": "https://example.com/season-1.jpg",
                "air_date": "2025-01-01",
            },
        ),
        201,
    )
    api_assertions.assert_error(
        api_client.post(
            f"/api/v1/media/{media['id']}/seasons",
            json={"season_number": 1},
        ),
        status_code=409,
        code="SEASON_NUMBER_CONFLICT",
    )

    episode_two = api_assertions.assert_status(
        api_client.post(
            f"/api/v1/seasons/{season['id']}/episodes",
            json={
                "episode_number": 2,
                "title": "Second Episode",
                "duration_minutes": 48,
            },
        ),
        201,
    )
    episode_one = api_assertions.assert_status(
        api_client.post(
            f"/api/v1/seasons/{season['id']}/episodes",
            json={
                "episode_number": 1,
                "title": "Pilot",
                "thumbnail_url": "https://example.com/pilot.jpg",
            },
        ),
        201,
    )
    episodes = api_assertions.assert_status(
        api_client.get(f"/api/v1/seasons/{season['id']}/episodes"),
        200,
    )
    assert [episode["id"] for episode in episodes] == [
        episode_one["id"],
        episode_two["id"],
    ]

    updated = api_assertions.assert_status(
        api_client.patch(
            f"/api/v1/episodes/{episode_two['id']}",
            json={"title": "Updated Second Episode", "duration_minutes": 50},
        ),
        200,
    )
    assert updated["title"] == "Updated Second Episode"
    assert updated["duration_minutes"] == 50

    api_assertions.assert_error(
        api_client.patch(
            f"/api/v1/episodes/{episode_two['id']}",
            json={"episode_number": 1},
        ),
        status_code=409,
        code="EPISODE_NUMBER_CONFLICT",
    )

    api_assertions.assert_status(
        api_client.delete(f"/api/v1/seasons/{season['id']}"),
        204,
    )
    api_assertions.assert_error(
        api_client.delete(f"/api/v1/episodes/{episode_one['id']}"),
        status_code=404,
        code="EPISODE_NOT_FOUND",
    )


def test_only_series_can_have_seasons(
    api_client: TestClient,
    api_assertions: ApiAssertions,
):
    movie = api_assertions.assert_status(
        api_client.post("/api/v1/media", json={"title": "Movie"}),
        201,
    )

    api_assertions.assert_error(
        api_client.post(
            f"/api/v1/media/{movie['id']}/seasons",
            json={"season_number": 1},
        ),
        status_code=400,
        code="SEASON_REQUIRES_SERIES",
    )
