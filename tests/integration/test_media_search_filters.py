import pytest
from fastapi.testclient import TestClient

from tests.support.api import ApiAssertions
from videocenter.models.media import MediaStatus, MediaType

pytestmark = pytest.mark.integration


def test_title_fuzzy_search_checks_all_title_fields(
    api_client: TestClient,
    model_factory,
):
    primary = model_factory.media(title="The Wandering Earth")
    original = model_factory.media(
        title="流浪地球",
        original_title="Wandering Earth",
    )
    alias = model_factory.media(
        title="Alias Target",
        alternative_titles=["Earth Journey"],
    )
    model_factory.media(title="Unrelated Movie")

    response = api_client.get(
        "/api/v1/media",
        params={"query": "earth", "page_size": 20},
    )

    assert response.status_code == 200
    assert {item["id"] for item in response.json()["items"]} == {
        primary.id,
        original.id,
        alias.id,
    }


def test_media_filters_can_be_combined(
    api_client: TestClient,
    model_factory,
):
    expected = model_factory.media(
        title="Expected",
        media_type=MediaType.DOCUMENTARY,
        release_year=2024,
        status=MediaStatus.AVAILABLE,
        source_site="Example Video",
    )
    model_factory.media(
        title="Wrong type",
        media_type=MediaType.MOVIE,
        release_year=2024,
        status=MediaStatus.AVAILABLE,
        source_site="Example Video",
    )
    model_factory.media(
        title="Wrong year",
        media_type=MediaType.DOCUMENTARY,
        release_year=2023,
        status=MediaStatus.AVAILABLE,
        source_site="Example Video",
    )

    response = api_client.get(
        "/api/v1/media",
        params={
            "media_type": "documentary",
            "release_year": 2024,
            "status": "available",
            "source_site": "example video",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == expected.id


def test_media_sorting_supports_whitelisted_fields(
    api_client: TestClient,
    model_factory,
):
    low = model_factory.media(
        title="Zulu",
        release_year=2020,
        rating=6.0,
    )
    high = model_factory.media(
        title="Alpha",
        release_year=2024,
        rating=9.0,
    )
    middle = model_factory.media(
        title="Middle",
        release_year=2022,
        rating=7.5,
    )

    by_year = api_client.get(
        "/api/v1/media",
        params={"sort_by": "release_year", "sort_order": "asc"},
    ).json()
    assert [item["id"] for item in by_year["items"]] == [
        low.id,
        middle.id,
        high.id,
    ]

    by_title = api_client.get(
        "/api/v1/media",
        params={"sort_by": "title", "sort_order": "asc"},
    ).json()
    assert [item["id"] for item in by_title["items"]] == [
        high.id,
        middle.id,
        low.id,
    ]


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"media_type": "invalid"}, "media_type"),
        ({"release_year": 1800}, "release_year"),
        ({"status": "invalid"}, "status"),
        ({"source_site": "   "}, "source_site"),
        ({"sort_by": "drop_table"}, "sort_by"),
        ({"sort_order": "random"}, "sort_order"),
    ],
)
def test_media_filters_and_sorting_reject_invalid_values(
    api_client: TestClient,
    api_assertions: ApiAssertions,
    params,
    field,
):
    api_assertions.assert_validation_error(
        api_client.get("/api/v1/media", params=params),
        ["query", field],
    )


def test_media_detail_returns_resources_tags_and_season_hierarchy(
    api_client: TestClient,
    model_factory,
):
    media = model_factory.media(
        title="Detailed Series",
        media_type=MediaType.SERIES,
    )
    resource = model_factory.local_resource(media=media)
    tag = model_factory.tag(name="Detailed")
    media.tags.append(tag)
    model_factory.session.commit()
    season = model_factory.season(media=media, season_number=1)
    episode = model_factory.episode(season=season, episode_number=1)

    response = api_client.get(f"/api/v1/media/{media.id}")

    assert response.status_code == 200
    detail = response.json()
    assert detail["resources"][0]["id"] == resource.id
    assert detail["tags"][0]["id"] == tag.id
    assert detail["seasons"][0]["id"] == season.id
    assert detail["seasons"][0]["episodes"][0]["id"] == episode.id
