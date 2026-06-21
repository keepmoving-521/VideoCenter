import threading
import time

from videocenter.services.hls import HlsTaskQueue


def test_hls_queue_limits_concurrent_tasks():
    release = threading.Event()
    lock = threading.Lock()
    running = 0
    maximum_running = 0

    def runner(task_id):
        nonlocal running, maximum_running
        with lock:
            running += 1
            maximum_running = max(maximum_running, running)
        release.wait(timeout=2)
        with lock:
            running -= 1

    task_queue = HlsTaskQueue(runner, worker_count=2)
    try:
        for task_id in range(1, 6):
            assert task_queue.enqueue(task_id)
        assert task_queue.enqueue(1) is False
        deadline = time.time() + 2
        while task_queue.running_count < 2 and time.time() < deadline:
            time.sleep(0.01)
        assert task_queue.running_count == 2
        assert task_queue.waiting_count == 3
        release.set()
        task_queue.join()
        assert maximum_running == 2
    finally:
        release.set()
        task_queue.shutdown()
