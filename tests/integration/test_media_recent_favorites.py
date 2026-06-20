from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from tests.support.api import ApiAssertions

pytestmark = pytest.mark.integration


def test_recent_media_is_paginated_by_created_time(
    api_client: TestClient,
    api_assertions: ApiAssertions,
    model_factory,
):
    now = datetime.now()
    oldest = model_factory.media(
        title="Oldest",
        created_at=now - timedelta(days=2),
    )
    newest = model_factory.media(
        title="Newest",
        created_at=now,
    )
    middle = model_factory.media(
        title="Middle",
        created_at=now - timedelta(days=1),
    )

    first_page = api_assertions.assert_status(
        api_client.get(
            "/api/v1/media/recent",
            params={"page": 1, "page_size": 2},
        ),
        200,
    )
    assert [item["id"] for item in first_page["items"]] == [newest.id, middle.id]
    assert first_page["total"] == 3
    assert first_page["total_pages"] == 2
    assert first_page["has_next"] is True
    assert first_page["has_previous"] is False

    second_page = api_client.get(
        "/api/v1/media/recent",
        params={"page": 2, "page_size": 2},
    ).json()
    assert [item["id"] for item in second_page["items"]] == [oldest.id]
    assert second_page["has_next"] is False
    assert second_page["has_previous"] is True


def test_favorite_media_only_returns_favorites(
    api_client: TestClient,
    model_factory,
):
    now = datetime.now()
    older_favorite = model_factory.media(
        title="Older Favorite",
        is_favorite=True,
        created_at=now - timedelta(days=1),
    )
    model_factory.media(
        title="Not Favorite",
        is_favorite=False,
        created_at=now + timedelta(days=1),
    )
    newer_favorite = model_factory.media(
        title="Newer Favorite",
        is_favorite=True,
        created_at=now,
    )

    response = api_client.get("/api/v1/media/favorites")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert [item["id"] for item in payload["items"]] == [
        newer_favorite.id,
        older_favorite.id,
    ]
    assert all(item["is_favorite"] for item in payload["items"])


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/media/recent",
        "/api/v1/media/favorites",
    ],
)
def test_recent_and_favorite_lists_validate_pagination(
    api_client: TestClient,
    api_assertions: ApiAssertions,
    path: str,
):
    api_assertions.assert_validation_error(
        api_client.get(path, params={"page_size": 201}),
        ["query", "page_size"],
    )
