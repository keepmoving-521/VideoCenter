from videocenter.models.hls import HlsTask, HlsTaskStatus
from videocenter.services.hls import restore_hls_tasks


def test_restore_hls_tasks_requeues_waiting_and_running(
    db_session,
    model_factory,
    monkeypatch,
):
    resource = model_factory.local_resource()
    waiting = HlsTask(
        resource_id=resource.id,
        status=HlsTaskStatus.WAITING,
    )
    running = HlsTask(
        resource_id=resource.id,
        status=HlsTaskStatus.RUNNING,
        progress=40,
    )
    completed = HlsTask(
        resource_id=resource.id,
        status=HlsTaskStatus.COMPLETED,
        progress=100,
    )
    db_session.add_all([waiting, running, completed])
    db_session.commit()
    started: list[int] = []
    monkeypatch.setattr("videocenter.services.hls.start_hls_task", started.append)

    restored = restore_hls_tasks()

    assert restored == 2
    assert started == [waiting.id, running.id]
    db_session.expire_all()
    recovered = db_session.get(HlsTask, running.id)
    assert recovered.status == HlsTaskStatus.WAITING
    assert recovered.progress == 0
    assert db_session.get(HlsTask, completed.id).status == HlsTaskStatus.COMPLETED
