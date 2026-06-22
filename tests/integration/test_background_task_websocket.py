import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from videocenter.models.background_task import (
    BackgroundTask,
    BackgroundTaskStatus,
    BackgroundTaskType,
)
from videocenter.services.background_tasks import record_background_task_log

pytestmark = pytest.mark.integration


def test_websocket_pushes_task_events(
    api_client: TestClient,
    db_session: Session,
):
    with api_client.websocket_connect("/api/v1/tasks/ws") as websocket:
        assert websocket.receive_json() == {
            "type": "connected",
            "task_type": None,
            "status": None,
        }
        task = BackgroundTask(
            task_type=BackgroundTaskType.MEDIA_SCAN,
            title="WebSocket scan",
            status=BackgroundTaskStatus.RUNNING,
            progress=35,
            processed_items=7,
            total_items=20,
        )
        db_session.add(task)
        db_session.flush()
        record_background_task_log(
            db_session,
            task,
            event="progress",
            message="扫描进度更新",
            details={"processed_files": 7},
        )
        db_session.commit()

        event = websocket.receive_json()

        assert event["type"] == "task_event"
        assert event["event"] == "progress"
        assert event["message"] == "扫描进度更新"
        assert event["details"] == {"processed_files": 7}
        assert event["task"]["id"] == task.id
        assert event["task"]["task_type"] == "media_scan"
        assert event["task"]["status"] == "running"
        assert event["task"]["progress"] == 35
        assert event["task"]["processed_items"] == 7
        assert event["task"]["total_items"] == 20


def test_websocket_filters_task_type_and_status(
    api_client: TestClient,
    db_session: Session,
):
    with api_client.websocket_connect(
        "/api/v1/tasks/ws?task_type=download&status=running"
    ) as websocket:
        assert websocket.receive_json() == {
            "type": "connected",
            "task_type": "download",
            "status": "running",
        }
        ignored = BackgroundTask(
            task_type=BackgroundTaskType.MEDIA_SCAN,
            title="Ignored scan",
            status=BackgroundTaskStatus.RUNNING,
        )
        matched = BackgroundTask(
            task_type=BackgroundTaskType.DOWNLOAD,
            title="Matched download",
            status=BackgroundTaskStatus.RUNNING,
            progress=50,
        )
        db_session.add_all([ignored, matched])
        db_session.flush()
        record_background_task_log(
            db_session,
            ignored,
            event="running",
            message="ignored",
        )
        record_background_task_log(
            db_session,
            matched,
            event="running",
            message="matched",
        )
        db_session.commit()

        event = websocket.receive_json()

        assert event["message"] == "matched"
        assert event["task"]["id"] == matched.id


def test_websocket_supports_ping(
    api_client: TestClient,
):
    with api_client.websocket_connect("/api/v1/tasks/ws") as websocket:
        websocket.receive_json()
        websocket.send_text("ping")

        response = websocket.receive_json()

        assert response["type"] == "pong"
        assert response["sent_at"]


def test_websocket_rejects_invalid_filter(
    api_client: TestClient,
):
    with api_client.websocket_connect("/api/v1/tasks/ws?task_type=invalid") as websocket:
        error = websocket.receive_json()
        assert error == {
            "type": "error",
            "code": "INVALID_TASK_EVENT_FILTER",
            "message": "任务类型或状态筛选值无效",
        }
        with pytest.raises(WebSocketDisconnect) as exc_info:
            websocket.receive_json()
        assert exc_info.value.code == 1008
