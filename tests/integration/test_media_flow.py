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
                "sort_title": "Integration Movie, The",
                "original_title": "Integration Original",
                "alternative_titles": [
                    "Integration Alias",
                    " integration alias ",
                    "第二片名",
                ],
                "media_type": "documentary",
                "status": "available",
                "release_date": "2024-05-20",
                "content_rating": "PG-13",
                "source_site": "Example Video",
                "source_page_url": "https://example.com/videos/integration",
                "directors": ["Director One", " director one "],
                "actors": ["Actor One", "Actor Two"],
                "regions": ["中国大陆", "China"],
                "languages": ["汉语普通话", "English"],
                "genres": ["纪录片", "Technology"],
                "duration_minutes": 95,
                "rating": 8.6,
                "is_favorite": True,
                "personal_rating": 9.4,
                "personal_notes": "  值得反复观看。  ",
            },
        ),
        201,
    )
    assert created is not None
    media_id = created["id"]
    assert created["sort_title"] == "Integration Movie, The"
    assert created["alternative_titles"] == ["Integration Alias", "第二片名"]
    assert created["release_date"] == "2024-05-20"
    assert created["release_year"] == 2024
    assert created["content_rating"] == "PG-13"
    assert created["media_type"] == "documentary"
    assert created["status"] == "available"
    assert created["source_site"] == "Example Video"
    assert created["source_page_url"] == "https://example.com/videos/integration"
    assert created["directors"] == ["Director One"]
    assert created["actors"] == ["Actor One", "Actor Two"]
    assert created["regions"] == ["中国大陆", "China"]
    assert created["languages"] == ["汉语普通话", "English"]
    assert created["genres"] == ["纪录片", "Technology"]
    assert created["duration_minutes"] == 95
    assert created["rating"] == 8.6
    assert created["is_favorite"] is True
    assert created["personal_rating"] == 9.4
    assert created["personal_notes"] == "值得反复观看。"

    listed = api_assertions.assert_status(
        api_client.get("/api/v1/media", params={"query": "Integration"}),
        200,
    )
    assert listed is not None
    assert [item["id"] for item in listed] == [media_id]

    favorites = api_assertions.assert_status(
        api_client.get("/api/v1/media", params={"is_favorite": "true"}),
        200,
    )
    assert [item["id"] for item in favorites] == [media_id]

    updated = api_assertions.assert_status(
        api_client.patch(
            f"/api/v1/media/{media_id}",
            json={
                "title": "Updated Integration Movie",
                "alternative_titles": ["Updated Alias"],
                "release_date": "2025-01-01",
                "status": "archived",
                "rating": 9.1,
                "is_favorite": False,
                "personal_rating": 8.8,
                "personal_notes": "更新后的个人备注",
            },
        ),
        200,
    )
    assert updated is not None
    assert updated["title"] == "Updated Integration Movie"
    assert updated["alternative_titles"] == ["Updated Alias"]
    assert updated["release_year"] == 2025
    assert updated["status"] == "archived"
    assert updated["rating"] == 9.1
    assert updated["is_favorite"] is False
    assert updated["personal_rating"] == 8.8
    assert updated["personal_notes"] == "更新后的个人备注"

    favorites = api_assertions.assert_status(
        api_client.get("/api/v1/media", params={"is_favorite": "true"}),
        200,
    )
    assert favorites == []

    cleared = api_assertions.assert_status(
        api_client.patch(
            f"/api/v1/media/{media_id}",
            json={"personal_rating": None, "personal_notes": "   "},
        ),
        200,
    )
    assert cleared["personal_rating"] is None
    assert cleared["personal_notes"] is None

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
