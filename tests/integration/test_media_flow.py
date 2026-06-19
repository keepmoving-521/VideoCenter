import pytest
from fastapi.testclient import TestClient

from tests.support.api import ApiAssertions

pytestmark = pytest.mark.integration


def test_media_crud_flow(
    api_client: TestClient,
    api_assertions: ApiAssertions,
):
    created = api_assertions.assert_status(
        api_client.post(
            "/api/v1/media",
            json={
                "title": "Integration Movie",
                "media_type": "movie",
                "release_year": 2024,
            },
        ),
        201,
    )
    assert created is not None
    media_id = created["id"]

    listed = api_assertions.assert_status(
        api_client.get("/api/v1/media", params={"query": "Integration"}),
        200,
    )
    assert listed is not None
    assert [item["id"] for item in listed] == [media_id]

    updated = api_assertions.assert_status(
        api_client.patch(
            f"/api/v1/media/{media_id}",
            json={"title": "Updated Integration Movie"},
        ),
        200,
    )
    assert updated is not None
    assert updated["title"] == "Updated Integration Movie"

    api_assertions.assert_status(
        api_client.delete(f"/api/v1/media/{media_id}"),
        204,
    )
    api_assertions.assert_error(
        api_client.get(f"/api/v1/media/{media_id}"),
        status_code=404,
        code="MEDIA_NOT_FOUND",
    )


def test_model_factory_data_is_visible_through_api(
    api_client: TestClient,
    model_factory,
):
    media = model_factory.media(title="Factory Movie")
    resource = model_factory.local_resource(media=media)
    model_factory.watch_history(media=media, resource=resource)

    response = api_client.get("/api/v1/history")

    assert response.status_code == 200
    assert response.json()[0]["media_id"] == media.id
    assert response.json()[0]["resource_id"] == resource.id
