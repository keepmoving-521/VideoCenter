import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.support.api import ApiAssertions
from videocenter.models.download import DownloadTask
from videocenter.models.history import WatchHistory
from videocenter.models.media import Episode, LocalResource, Media, MediaType, Season

pytestmark = pytest.mark.integration


def test_media_edit_returns_complete_detail(
    api_client: TestClient,
    model_factory,
):
    media = model_factory.media(title="Original", media_type=MediaType.SERIES)
    season = model_factory.season(media=media)
    model_factory.episode(season=season)

    response = api_client.patch(
        f"/api/v1/media/{media.id}",
        json={
            "title": "Edited Series",
            "description": "Edited description",
            "is_favorite": True,
            "personal_rating": 9.2,
        },
    )

    assert response.status_code == 200
    detail = response.json()
    assert detail["title"] == "Edited Series"
    assert detail["description"] == "Edited description"
    assert detail["is_favorite"] is True
    assert detail["personal_rating"] == 9.2
    assert detail["seasons"][0]["episodes"][0]["title"] == "Episode 1"


def test_series_with_seasons_cannot_change_to_movie(
    api_client: TestClient,
    api_assertions: ApiAssertions,
    model_factory,
):
    media = model_factory.media(title="Series", media_type=MediaType.SERIES)
    model_factory.season(media=media)

    api_assertions.assert_error(
        api_client.patch(
            f"/api/v1/media/{media.id}",
            json={"media_type": "movie"},
        ),
        status_code=409,
        code="MEDIA_TYPE_HAS_SEASONS",
    )


def test_media_delete_cleans_relations_without_deleting_local_file_record(
    api_client: TestClient,
    db_session: Session,
    model_factory,
):
    media = model_factory.media(title="Delete Me", media_type=MediaType.SERIES)
    resource = model_factory.local_resource(media=media)
    download = model_factory.download_task(media=media)
    model_factory.watch_history(media=media, resource=resource)
    season = model_factory.season(media=media)
    episode = model_factory.episode(season=season)
    media_id = media.id
    resource_id = resource.id
    download_id = download.id
    season_id = season.id
    episode_id = episode.id

    response = api_client.delete(f"/api/v1/media/{media_id}")

    assert response.status_code == 204
    db_session.expire_all()
    assert db_session.get(Media, media_id) is None
    assert db_session.get(Season, season_id) is None
    assert db_session.get(Episode, episode_id) is None
    assert db_session.scalar(select(WatchHistory).where(WatchHistory.media_id == media_id)) is None
    preserved_resource = db_session.get(LocalResource, resource_id)
    assert preserved_resource is not None
    assert preserved_resource.media_id is None
    preserved_download = db_session.get(DownloadTask, download_id)
    assert preserved_download is not None
    assert preserved_download.media_id is None


def test_batch_delete_reports_deleted_and_missing_ids(
    api_client: TestClient,
    db_session: Session,
    model_factory,
):
    first = model_factory.media(title="First")
    second = model_factory.media(title="Second")
    untouched = model_factory.media(title="Untouched")
    first_id = first.id
    second_id = second.id
    untouched_id = untouched.id

    response = api_client.post(
        "/api/v1/media/batch-delete",
        json={
            "media_ids": [
                first_id,
                999999,
                second_id,
                first_id,
            ]
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "deleted_count": 2,
        "deleted_ids": [first_id, second_id],
        "missing_ids": [999999],
    }
    db_session.expire_all()
    assert db_session.get(Media, first_id) is None
    assert db_session.get(Media, second_id) is None
    assert db_session.get(Media, untouched_id) is not None


@pytest.mark.parametrize(
    "payload",
    [
        {"media_ids": []},
        {"media_ids": [0]},
        {"media_ids": list(range(1, 102))},
    ],
)
def test_batch_delete_validates_id_list(
    api_client: TestClient,
    api_assertions: ApiAssertions,
    payload,
):
    details = api_assertions.assert_error(
        api_client.post("/api/v1/media/batch-delete", json=payload),
        status_code=422,
        code="VALIDATION_ERROR",
    )["error"]["details"]
    assert any(item["loc"][:2] == ["body", "media_ids"] for item in details)
