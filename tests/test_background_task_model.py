import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from videocenter.models.background_task import (
    BackgroundTask,
    BackgroundTaskStatus,
    BackgroundTaskType,
)
from videocenter.schemas.background_task import BackgroundTaskRead


def test_background_task_defaults_and_read_schema(db_session: Session):
    task = BackgroundTask(
        task_type=BackgroundTaskType.MEDIA_SCAN,
        title="扫描媒体目录",
        source_task_id=12,
        total_items=10,
        task_payload={"path": "D:/Media"},
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)

    payload = BackgroundTaskRead.model_validate(task)

    assert payload.task_type == BackgroundTaskType.MEDIA_SCAN
    assert payload.status == BackgroundTaskStatus.WAITING
    assert payload.priority == 0
    assert payload.progress == 0
    assert payload.processed_items == 0
    assert payload.attempt == 1
    assert payload.max_attempts == 1
    assert payload.cancellable is True
    assert payload.pause_supported is False
    assert payload.cancel_requested is False
    assert payload.task_payload == {"path": "D:/Media"}


@pytest.mark.parametrize(
    "overrides",
    [
        {"progress": 101},
        {"priority": 101},
        {"processed_items": 2, "total_items": 1},
        {"attempt": 2, "max_attempts": 1},
    ],
)
def test_background_task_database_constraints(
    db_session: Session,
    overrides: dict,
):
    values = {
        "task_type": BackgroundTaskType.GENERIC,
        "title": "Invalid task",
    }
    values.update(overrides)
    db_session.add(BackgroundTask(**values))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_background_task_source_reference_is_unique_per_type(db_session: Session):
    db_session.add(
        BackgroundTask(
            task_type=BackgroundTaskType.DOWNLOAD,
            title="Download 1",
            source_task_id=1,
        )
    )
    db_session.commit()
    db_session.add(
        BackgroundTask(
            task_type=BackgroundTaskType.DOWNLOAD,
            title="Download duplicate",
            source_task_id=1,
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    db_session.add(
        BackgroundTask(
            task_type=BackgroundTaskType.MEDIA_SCAN,
            title="Scan 1",
            source_task_id=1,
        )
    )
    db_session.commit()
