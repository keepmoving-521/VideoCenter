import pytest
from fastapi.testclient import TestClient

from tests.support.api import ApiAssertions

pytestmark = pytest.mark.integration


def test_favorite_and_unfavorite_are_idempotent(
    api_client: TestClient,
    api_assertions: ApiAssertions,
    model_factory,
):
    media = model_factory.media(title="Favorite Movie")

    for _ in range(2):
        response = api_assertions.assert_status(
            api_client.put(f"/api/v1/media/{media.id}/favorite"),
            200,
        )
        assert response == {"media_id": media.id, "is_favorite": True}

    favorites = api_client.get(
        "/api/v1/media",
        params={"is_favorite": "true"},
    ).json()
    assert [item["id"] for item in favorites["items"]] == [media.id]

    for _ in range(2):
        response = api_assertions.assert_status(
            api_client.delete(f"/api/v1/media/{media.id}/favorite"),
            200,
        )
        assert response == {"media_id": media.id, "is_favorite": False}


def test_favorite_missing_media_returns_standard_error(
    api_client: TestClient,
    api_assertions: ApiAssertions,
):
    api_assertions.assert_error(
        api_client.put("/api/v1/media/999999/favorite"),
        status_code=404,
        code="MEDIA_NOT_FOUND",
    )


def test_tag_management_and_media_association_flow(
    api_client: TestClient,
    api_assertions: ApiAssertions,
    model_factory,
):
    media = model_factory.media(title="Tagged Movie")
    drama = api_client.post("/api/v1/tags", json={"name": "Drama"}).json()
    classic = api_client.post("/api/v1/tags", json={"name": "Classic"}).json()

    tags = api_assertions.assert_status(
        api_client.post(
            f"/api/v1/media/{media.id}/tags/{drama['id']}",
        ),
        200,
    )
    assert [tag["name"] for tag in tags] == ["Drama"]

    # Adding an existing association is deliberately idempotent.
    tags = api_client.post(
        f"/api/v1/media/{media.id}/tags/{drama['id']}",
    ).json()
    assert [tag["name"] for tag in tags] == ["Drama"]

    detail = api_assertions.assert_status(
        api_client.get(f"/api/v1/tags/{drama['id']}"),
        200,
    )
    assert detail["media_count"] == 1

    renamed = api_assertions.assert_status(
        api_client.patch(
            f"/api/v1/tags/{drama['id']}",
            json={"name": "Serious Drama"},
        ),
        200,
    )
    assert renamed["name"] == "Serious Drama"

    api_assertions.assert_error(
        api_client.patch(
            f"/api/v1/tags/{drama['id']}",
            json={"name": "classic"},
        ),
        status_code=409,
        code="TAG_ALREADY_EXISTS",
    )

    remaining = api_assertions.assert_status(
        api_client.delete(
            f"/api/v1/media/{media.id}/tags/{drama['id']}",
        ),
        200,
    )
    assert remaining == []
    assert api_client.get(f"/api/v1/tags/{drama['id']}").json()["media_count"] == 0

    api_assertions.assert_status(
        api_client.delete(f"/api/v1/tags/{classic['id']}"),
        204,
    )
    api_assertions.assert_error(
        api_client.get(f"/api/v1/tags/{classic['id']}"),
        status_code=404,
        code="TAG_NOT_FOUND",
    )


def test_deleting_tag_removes_association_but_keeps_media(
    api_client: TestClient,
    api_assertions: ApiAssertions,
    model_factory,
):
    media = model_factory.media(title="Keep Movie")
    tag = api_client.post("/api/v1/tags", json={"name": "Temporary"}).json()
    api_client.post(f"/api/v1/media/{media.id}/tags/{tag['id']}")

    api_assertions.assert_status(
        api_client.delete(f"/api/v1/tags/{tag['id']}"),
        204,
    )

    detail = api_assertions.assert_status(
        api_client.get(f"/api/v1/media/{media.id}"),
        200,
    )
    assert detail["title"] == "Keep Movie"
    assert detail["tags"] == []
