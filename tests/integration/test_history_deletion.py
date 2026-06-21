import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from videocenter.models.media import LocalResource, Media

pytestmark = pytest.mark.integration


def test_delete_single_watch_history(
    api_client: TestClient,
    api_assertions,
    db_session: Session,
    model_factory,
):
    media = model_factory.media()
    resource = model_factory.local_resource(media=media)
    model_factory.watch_history(media=media, resource=resource)

    assert api_client.delete(f"/api/v1/history/{media.id}").status_code == 204
    api_assertions.assert_error(
        api_client.get(f"/api/v1/history/{media.id}"),
        status_code=404,
        code="WATCH_HISTORY_NOT_FOUND",
    )
    api_assertions.assert_error(
        api_client.delete(f"/api/v1/history/{media.id}"),
        status_code=404,
        code="WATCH_HISTORY_NOT_FOUND",
    )
    assert db_session.get(Media, media.id) is not None
    assert db_session.get(LocalResource, resource.id) is not None


def test_batch_delete_watch_history_reports_deleted_and_missing_ids(
    api_client: TestClient,
    model_factory,
):
    first = model_factory.media()
    second = model_factory.media()
    preserved = model_factory.media()
    model_factory.watch_history(media=first)
    model_factory.watch_history(media=second)
    model_factory.watch_history(media=preserved)

    response = api_client.post(
        "/api/v1/history/batch-delete",
        json={"media_ids": [first.id, 999999, second.id, first.id]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "deleted_count": 2,
        "deleted_media_ids": [first.id, second.id],
        "missing_media_ids": [999999],
    }
    recent_ids = [
        item["media"]["id"] for item in api_client.get("/api/v1/history/recent").json()["items"]
    ]
    assert recent_ids == [preserved.id]


@pytest.mark.parametrize(
    "payload",
    [
        {"media_ids": []},
        {"media_ids": [1] * 101},
        {"media_ids": [0]},
    ],
)
def test_batch_delete_watch_history_validates_media_ids(
    api_client: TestClient,
    api_assertions,
    payload: dict,
):
    api_assertions.assert_error(
        api_client.post("/api/v1/history/batch-delete", json=payload),
        status_code=422,
        code="VALIDATION_ERROR",
    )


def test_clear_all_watch_history_is_idempotent(
    api_client: TestClient,
    model_factory,
):
    first = model_factory.media()
    second = model_factory.media()
    model_factory.watch_history(media=first)
    model_factory.watch_history(media=second)

    cleared = api_client.delete("/api/v1/history/clear")

    assert cleared.status_code == 200
    assert cleared.json() == {"deleted_count": 2}
    assert api_client.get("/api/v1/history/recent").json()["total"] == 0
    assert api_client.delete("/api/v1/history/clear").json() == {"deleted_count": 0}
