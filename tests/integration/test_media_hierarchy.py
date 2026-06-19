import pytest
from fastapi.testclient import TestClient

from tests.support.api import ApiAssertions

pytestmark = pytest.mark.integration


def test_media_season_episode_association_is_queryable(
    api_client: TestClient,
    api_assertions: ApiAssertions,
):
    media = api_assertions.assert_status(
        api_client.post(
            "/api/v1/media",
            json={"title": "Associated Series", "media_type": "series"},
        ),
        201,
    )
    second_season = api_assertions.assert_status(
        api_client.post(
            f"/api/v1/media/{media['id']}/seasons",
            json={"season_number": 2, "title": "Season Two"},
        ),
        201,
    )
    first_season = api_assertions.assert_status(
        api_client.post(
            f"/api/v1/media/{media['id']}/seasons",
            json={"season_number": 1, "title": "Season One"},
        ),
        201,
    )
    second_episode = api_assertions.assert_status(
        api_client.post(
            f"/api/v1/seasons/{first_season['id']}/episodes",
            json={"episode_number": 2, "title": "Episode Two"},
        ),
        201,
    )
    first_episode = api_assertions.assert_status(
        api_client.post(
            f"/api/v1/seasons/{first_season['id']}/episodes",
            json={"episode_number": 1, "title": "Episode One"},
        ),
        201,
    )

    hierarchy = api_assertions.assert_status(
        api_client.get(f"/api/v1/media/{media['id']}/hierarchy"),
        200,
    )
    assert hierarchy["media_id"] == media["id"]
    assert hierarchy["title"] == "Associated Series"
    assert [season["id"] for season in hierarchy["seasons"]] == [
        first_season["id"],
        second_season["id"],
    ]
    assert [episode["id"] for episode in hierarchy["seasons"][0]["episodes"]] == [
        first_episode["id"],
        second_episode["id"],
    ]
    assert hierarchy["seasons"][1]["episodes"] == []

    season_detail = api_assertions.assert_status(
        api_client.get(f"/api/v1/seasons/{first_season['id']}"),
        200,
    )
    assert season_detail["media_id"] == media["id"]
    assert [episode["season_id"] for episode in season_detail["episodes"]] == [
        first_season["id"],
        first_season["id"],
    ]

    episode_detail = api_assertions.assert_status(
        api_client.get(f"/api/v1/episodes/{first_episode['id']}"),
        200,
    )
    assert episode_detail["season_id"] == first_season["id"]
    assert episode_detail["season_number"] == 1
    assert episode_detail["media_id"] == media["id"]


def test_hierarchy_detail_endpoints_return_standard_not_found_errors(
    api_client: TestClient,
    api_assertions: ApiAssertions,
):
    api_assertions.assert_error(
        api_client.get("/api/v1/media/999999/hierarchy"),
        status_code=404,
        code="MEDIA_NOT_FOUND",
    )
    api_assertions.assert_error(
        api_client.get("/api/v1/seasons/999999"),
        status_code=404,
        code="SEASON_NOT_FOUND",
    )
    api_assertions.assert_error(
        api_client.get("/api/v1/episodes/999999"),
        status_code=404,
        code="EPISODE_NOT_FOUND",
    )
