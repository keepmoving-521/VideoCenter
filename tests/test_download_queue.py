import threading

from videocenter.services.download_queue import DownloadTaskQueue


def test_download_queue_processes_tasks_with_fixed_worker_count():
    first_started = threading.Event()
    release_first = threading.Event()
    processed: list[int] = []

    def runner(task_id, token):
        if task_id == 1:
            first_started.set()
            release_first.wait(timeout=2)
        if not token.is_cancelled:
            processed.append(task_id)

    task_queue = DownloadTaskQueue(runner, worker_count=1)
    try:
        assert task_queue.enqueue(1) is True
        assert first_started.wait(timeout=2)
        assert task_queue.enqueue(2) is True
        assert task_queue.enqueue(2) is False
        assert task_queue.running_count == 1
        assert task_queue.waiting_count == 1

        release_first.set()
        task_queue.join()

        assert processed == [1, 2]
        assert task_queue.running_count == 0
    finally:
        release_first.set()
        task_queue.shutdown()


def test_download_queue_can_cancel_waiting_task():
    first_started = threading.Event()
    release_first = threading.Event()
    processed: list[int] = []

    def runner(task_id, token):
        if task_id == 1:
            first_started.set()
            release_first.wait(timeout=2)
        if not token.is_cancelled:
            processed.append(task_id)

    task_queue = DownloadTaskQueue(runner, worker_count=1)
    try:
        task_queue.enqueue(1)
        assert first_started.wait(timeout=2)
        task_queue.enqueue(2)

        assert task_queue.cancel(2) is True
        release_first.set()
        task_queue.join()

        assert processed == [1]
        assert task_queue.contains(2) is False
    finally:
        release_first.set()
        task_queue.shutdown()


def test_download_queue_can_pause_and_resume_waiting_task():
    first_started = threading.Event()
    release_first = threading.Event()
    processed: list[int] = []

    def runner(task_id, token):
        if task_id == 1:
            first_started.set()
            release_first.wait(timeout=2)
        processed.append(task_id)

    task_queue = DownloadTaskQueue(runner, worker_count=1)
    try:
        task_queue.enqueue(1)
        assert first_started.wait(timeout=2)
        task_queue.enqueue(2)
        assert task_queue.pause(2) is True

        release_first.set()
        threading.Event().wait(0.05)
        assert processed == [1]

        assert task_queue.resume(2) is True
        task_queue.join()
        assert processed == [1, 2]
    finally:
        release_first.set()
        task_queue.shutdown()
