from videocenter.models.analysis import AnalysisTask, AnalysisTaskStatus
from videocenter.services.analysis_tasks import restore_analysis_tasks


def test_restore_analysis_tasks_requeues_waiting_and_running(
    db_session,
    monkeypatch,
):
    waiting = AnalysisTask(
        resource_ids=[1],
        status=AnalysisTaskStatus.WAITING,
        total_resources=1,
    )
    running = AnalysisTask(
        resource_ids=[2, 3],
        status=AnalysisTaskStatus.RUNNING,
        total_resources=2,
        processed_resources=1,
        progress=50,
        analyzed_resource_ids=[2],
    )
    completed = AnalysisTask(
        resource_ids=[4],
        status=AnalysisTaskStatus.COMPLETED,
        total_resources=1,
        processed_resources=1,
        progress=100,
    )
    db_session.add_all([waiting, running, completed])
    db_session.commit()
    started: list[int] = []
    monkeypatch.setattr(
        "videocenter.services.analysis_tasks.start_analysis_task",
        started.append,
    )

    restored = restore_analysis_tasks()

    assert restored == 2
    assert started == [waiting.id, running.id]
    db_session.expire_all()
    recovered = db_session.get(AnalysisTask, running.id)
    assert recovered.status == AnalysisTaskStatus.WAITING
    assert recovered.progress == 0
    assert recovered.processed_resources == 0
    assert recovered.analyzed_resource_ids == []
    assert db_session.get(AnalysisTask, completed.id).status == AnalysisTaskStatus.COMPLETED
