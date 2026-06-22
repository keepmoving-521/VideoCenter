import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.support.api import ApiAssertions
from videocenter.models.analysis import AnalysisTask, AnalysisTaskStatus
from videocenter.models.background_task import (
    BackgroundTask,
    BackgroundTaskStatus,
    BackgroundTaskType,
)
from videocenter.services.analysis_tasks import run_analysis_task

pytestmark = pytest.mark.integration


def test_batch_analysis_task_reports_progress_and_results(
    api_client: TestClient,
    db_session: Session,
    model_factory,
    monkeypatch,
):
    analyzed = model_factory.local_resource()
    skipped = model_factory.local_resource(
        media_info_probed=True,
        visual_assets_generated=False,
    )
    missing_file = model_factory.local_resource()
    monkeypatch.setattr(
        "videocenter.api.routes.local_resources.start_analysis_task",
        lambda task_id: None,
    )

    def fake_analyze(resource, *, force=False):
        if resource.id == analyzed.id:
            resource.video_codec = "hevc"
            return "analyzed"
        if resource.id == skipped.id:
            return "skipped"
        return "missing"

    monkeypatch.setattr(
        "videocenter.services.analysis_tasks.analyze_local_resource",
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

    assert response.status_code == 202
    created = response.json()
    assert created["status"] == "waiting"
    assert created["total_resources"] == 4
    background = db_session.scalar(
        select(BackgroundTask).where(
            BackgroundTask.task_type == BackgroundTaskType.MEDIA_ANALYSIS,
            BackgroundTask.source_task_id == created["id"],
        )
    )
    assert background is not None
    assert background.status == BackgroundTaskStatus.WAITING

    run_analysis_task(created["id"])
    detail = api_client.get(f"/api/v1/local-resources/analysis-tasks/{created['id']}").json()
    assert detail["status"] == "completed"
    assert detail["progress"] == 100
    assert detail["processed_resources"] == 4
    assert detail["analyzed_resource_ids"] == [analyzed.id]
    assert detail["skipped_resource_ids"] == [skipped.id]
    assert detail["missing_resource_ids"] == [missing_file.id, 999999]
    assert detail["failures"] == []
    assert api_client.get("/api/v1/local-resources/analysis-tasks").json()[0]["id"] == created["id"]
    db_session.refresh(analyzed)
    assert analyzed.video_codec == "hevc"
    db_session.refresh(background)
    assert background.status == BackgroundTaskStatus.COMPLETED
    assert background.processed_items == 4
    assert background.total_items == 4
    assert background.task_result["analyzed_resource_ids"] == [analyzed.id]


def test_analysis_failure_can_be_retried_as_new_task(
    api_client: TestClient,
    db_session: Session,
    model_factory,
    monkeypatch,
):
    first = model_factory.local_resource()
    second = model_factory.local_resource()
    monkeypatch.setattr(
        "videocenter.api.routes.local_resources.start_analysis_task",
        lambda task_id: None,
    )

    def fail_second(resource, *, force=False):
        if resource.id == second.id:
            resource.video_codec = "should-rollback"
            raise RuntimeError("analysis failed")
        resource.video_codec = "h264"
        return "analyzed"

    monkeypatch.setattr(
        "videocenter.services.analysis_tasks.analyze_local_resource",
        fail_second,
    )
    created = api_client.post(
        "/api/v1/local-resources/batch-analyze",
        json={"resource_ids": [first.id, second.id], "force": True},
    ).json()
    run_analysis_task(created["id"])

    failed_detail = api_client.get(f"/api/v1/local-resources/analysis-tasks/{created['id']}").json()
    assert failed_detail["status"] == "completed"
    assert failed_detail["failures"] == [{"resource_id": second.id, "error": "analysis failed"}]
    db_session.refresh(second)
    assert second.video_codec is None

    retry_response = api_client.post(
        f"/api/v1/local-resources/analysis-tasks/{created['id']}/retry"
    )
    assert retry_response.status_code == 202
    retry = retry_response.json()
    assert retry["retry_of_task_id"] == created["id"]
    assert retry["resource_ids"] == [second.id]
    assert retry["force"] is True
    assert retry["status"] == "waiting"
    original_background = db_session.scalar(
        select(BackgroundTask).where(
            BackgroundTask.task_type == BackgroundTaskType.MEDIA_ANALYSIS,
            BackgroundTask.source_task_id == created["id"],
        )
    )
    retry_background = db_session.scalar(
        select(BackgroundTask).where(
            BackgroundTask.task_type == BackgroundTaskType.MEDIA_ANALYSIS,
            BackgroundTask.source_task_id == retry["id"],
        )
    )
    assert retry_background is not None
    assert retry_background.parent_task_id == original_background.id
    assert retry_background.attempt == original_background.attempt + 1


def test_analysis_task_not_retryable_and_not_found(
    api_client: TestClient,
    db_session: Session,
    api_assertions: ApiAssertions,
):
    task = AnalysisTask(
        resource_ids=[1],
        force=False,
        status=AnalysisTaskStatus.COMPLETED,
        total_resources=1,
        processed_resources=1,
        progress=100,
    )
    db_session.add(task)
    db_session.commit()

    api_assertions.assert_error(
        api_client.post(f"/api/v1/local-resources/analysis-tasks/{task.id}/retry"),
        status_code=409,
        code="ANALYSIS_TASK_NOT_RETRYABLE",
    )
    api_assertions.assert_error(
        api_client.get("/api/v1/local-resources/analysis-tasks/999999"),
        status_code=404,
        code="ANALYSIS_TASK_NOT_FOUND",
    )


@pytest.mark.parametrize("resource_ids", [[], [0], list(range(1, 102))])
def test_batch_analysis_validates_resource_ids(
    api_client: TestClient,
    resource_ids,
):
    response = api_client.post(
        "/api/v1/local-resources/batch-analyze",
        json={"resource_ids": resource_ids},
    )

    assert response.status_code == 422
