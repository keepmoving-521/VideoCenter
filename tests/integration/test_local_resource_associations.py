import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.support.api import ApiAssertions
from videocenter.models.media import MediaStatus

pytestmark = pytest.mark.integration


def test_associate_and_unlink_local_resource(
    api_client: TestClient,
    db_session: Session,
    model_factory,
):
    media = model_factory.media(status=MediaStatus.PENDING)
    resource = model_factory.local_resource()

    response = api_client.put(
        f"/api/v1/local-resources/{resource.id}/association",
        json={"media_id": media.id},
    )

    assert response.status_code == 200
    assert response.json()["media_id"] == media.id
    db_session.refresh(media)
    assert media.status == MediaStatus.AVAILABLE

    response = api_client.put(
        f"/api/v1/local-resources/{resource.id}/association",
        json={"media_id": None},
    )

    assert response.status_code == 200
    assert response.json()["media_id"] is None
    db_session.refresh(media)
    assert media.status == MediaStatus.PENDING


def test_reassociation_updates_old_and_new_media_status(
    api_client: TestClient,
    db_session: Session,
    model_factory,
):
    old_media = model_factory.media(status=MediaStatus.AVAILABLE)
    new_media = model_factory.media(status=MediaStatus.PENDING)
    resource = model_factory.local_resource(media=old_media)

    response = api_client.put(
        f"/api/v1/local-resources/{resource.id}/association",
        json={"media_id": new_media.id},
    )

    assert response.status_code == 200
    db_session.refresh(old_media)
    db_session.refresh(new_media)
    assert old_media.status == MediaStatus.PENDING
    assert new_media.status == MediaStatus.AVAILABLE


def test_batch_associate_reports_missing_and_deduplicates_ids(
    api_client: TestClient,
    db_session: Session,
    model_factory,
):
    media = model_factory.media()
    first = model_factory.local_resource()
    second = model_factory.local_resource()

    response = api_client.post(
        "/api/v1/local-resources/batch-associate",
        json={
            "resource_ids": [first.id, 999999, second.id, first.id],
            "media_id": media.id,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "media_id": media.id,
        "associated_count": 2,
        "associated_resource_ids": [first.id, second.id],
        "missing_resource_ids": [999999],
    }
    db_session.refresh(first)
    db_session.refresh(second)
    assert first.media_id == media.id
    assert second.media_id == media.id


@pytest.mark.parametrize(
    ("url", "payload", "code"),
    [
        (
            "/api/v1/local-resources/999999/association",
            {"media_id": None},
            "LOCAL_RESOURCE_NOT_FOUND",
        ),
        (
            "/api/v1/local-resources/1/association",
            {"media_id": 999999},
            "MEDIA_NOT_FOUND",
        ),
        (
            "/api/v1/local-resources/batch-associate",
            {"resource_ids": [999999], "media_id": 999999},
            "MEDIA_NOT_FOUND",
        ),
    ],
)
def test_association_not_found_errors(
    api_client: TestClient,
    api_assertions: ApiAssertions,
    url,
    payload,
    code,
):
    method = api_client.post if url.endswith("batch-associate") else api_client.put
    api_assertions.assert_error(
        method(url, json=payload),
        status_code=404,
        code=code,
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"resource_ids": [], "media_id": None},
        {"resource_ids": [0], "media_id": None},
        {"resource_ids": list(range(1, 102)), "media_id": None},
    ],
)
def test_batch_association_validates_resource_ids(
    api_client: TestClient,
    api_assertions: ApiAssertions,
    payload,
):
    details = api_assertions.assert_error(
        api_client.post("/api/v1/local-resources/batch-associate", json=payload),
        status_code=422,
        code="VALIDATION_ERROR",
    )["error"]["details"]
    assert any(item["loc"][:2] == ["body", "resource_ids"] for item in details)
