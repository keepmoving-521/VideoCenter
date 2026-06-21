from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_batch_analysis_reports_analyzed_skipped_and_missing(
    api_client: TestClient,
    model_factory,
    monkeypatch,
):
    analyzed = model_factory.local_resource(
        media_info_probed=False,
        visual_assets_generated=None,
    )
    skipped = model_factory.local_resource(
        media_info_probed=True,
        visual_assets_generated=False,
    )
    missing_file = model_factory.local_resource(
        file_path=str(Path("data/media/missing-batch-analysis.mp4").resolve()),
        media_info_probed=False,
        visual_assets_generated=None,
    )

    def fake_analyze(resource, *, force=False):
        if resource.id == analyzed.id:
            resource.media_info_probed = True
            resource.video_codec = "hevc"
            return "analyzed"
        if resource.id == skipped.id:
            return "analyzed" if force else "skipped"
        return "missing"

    monkeypatch.setattr(
        "videocenter.api.routes.local_resources.analyze_local_resource",
        fake_analyze,
    )

    response = api_client.post(
        "/api/v1/local-resources/batch-analyze",
        json={
            "resource_ids": [
                analyzed.id,
                skipped.id,
                missing_file.id,
                999999,
                analyzed.id,
            ]
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "requested_count": 4,
        "analyzed_count": 1,
        "analyzed_resource_ids": [analyzed.id],
        "skipped_resource_ids": [skipped.id],
        "missing_resource_ids": [missing_file.id, 999999],
        "failures": [],
    }


def test_batch_analysis_force_and_partial_failure(
    api_client: TestClient,
    db_session,
    model_factory,
    monkeypatch,
):
    first = model_factory.local_resource(
        media_info_probed=True,
        visual_assets_generated=False,
    )
    second = model_factory.local_resource()

    def fake_analyze(resource, *, force=False):
        assert force is True
        if resource.id == second.id:
            resource.video_codec = "should-rollback"
            raise RuntimeError("analysis failed")
        resource.video_codec = "hevc"
        return "analyzed"

    monkeypatch.setattr(
        "videocenter.api.routes.local_resources.analyze_local_resource",
        fake_analyze,
    )

    response = api_client.post(
        "/api/v1/local-resources/batch-analyze",
        json={"resource_ids": [first.id, second.id], "force": True},
    )

    assert response.status_code == 200
    assert response.json()["analyzed_resource_ids"] == [first.id]
    assert response.json()["failures"] == [{"resource_id": second.id, "error": "analysis failed"}]
    db_session.refresh(first)
    db_session.refresh(second)
    assert first.video_codec == "hevc"
    assert second.video_codec is None


@pytest.mark.parametrize(
    "resource_ids",
    [[], [0], list(range(1, 102))],
)
def test_batch_analysis_validates_resource_ids(
    api_client: TestClient,
    resource_ids,
):
    response = api_client.post(
        "/api/v1/local-resources/batch-analyze",
        json={"resource_ids": resource_ids},
    )

    assert response.status_code == 422
