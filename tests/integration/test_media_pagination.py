import pytest
from fastapi.testclient import TestClient

from tests.support.api import ApiAssertions

pytestmark = pytest.mark.integration


def test_media_list_returns_paginated_response(
    api_client: TestClient,
    api_assertions: ApiAssertions,
    model_factory,
):
    media = [model_factory.media(title=f"Page Movie {index}") for index in range(1, 6)]

    first_page = api_assertions.assert_status(
        api_client.get(
            "/api/v1/media",
            params={"page": 1, "page_size": 2},
        ),
        200,
    )
    assert [item["id"] for item in first_page["items"]] == [
        media[4].id,
        media[3].id,
    ]
    assert first_page == {
        **first_page,
        "total": 5,
        "page": 1,
        "page_size": 2,
        "total_pages": 3,
        "has_next": True,
        "has_previous": False,
    }

    last_page = api_assertions.assert_status(
        api_client.get(
            "/api/v1/media",
            params={"page": 3, "page_size": 2},
        ),
        200,
    )
    assert [item["id"] for item in last_page["items"]] == [media[0].id]
    assert last_page["has_next"] is False
    assert last_page["has_previous"] is True


def test_media_pagination_total_respects_filters(
    api_client: TestClient,
    model_factory,
):
    model_factory.media(title="Favorite Match", is_favorite=True)
    model_factory.media(title="Favorite Other", is_favorite=True)
    model_factory.media(title="Ordinary Match", is_favorite=False)

    response = api_client.get(
        "/api/v1/media",
        params={
            "query": "Match",
            "is_favorite": "true",
            "page": 1,
            "page_size": 10,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["total_pages"] == 1
    assert [item["title"] for item in payload["items"]] == ["Favorite Match"]


def test_media_pagination_page_beyond_last_is_empty(
    api_client: TestClient,
    model_factory,
):
    model_factory.media(title="Only Movie")

    response = api_client.get(
        "/api/v1/media",
        params={"page": 10, "page_size": 5},
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 1,
        "page": 10,
        "page_size": 5,
        "total_pages": 1,
        "has_next": False,
        "has_previous": True,
    }


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page_size": 0},
        {"page_size": 201},
    ],
)
def test_media_pagination_rejects_invalid_parameters(
    api_client: TestClient,
    api_assertions: ApiAssertions,
    params,
):
    response = api_client.get("/api/v1/media", params=params)

    field = next(iter(params))
    api_assertions.assert_validation_error(response, ["query", field])
