import queue
import threading
from collections.abc import Callable

from videocenter.services.downloaders import DownloadCancellationToken

DownloadRunner = Callable[[int, DownloadCancellationToken], None]


class DownloadTaskQueue:
    """Fixed-size in-process worker queue for download task IDs."""

    def __init__(self, runner: DownloadRunner, *, worker_count: int = 1) -> None:
        if worker_count < 1:
            raise ValueError("worker_count must be greater than zero")
        self._runner = runner
        self._queue: queue.Queue[int | None] = queue.Queue()
        self._tokens: dict[int, DownloadCancellationToken] = {}
        self._running_ids: set[int] = set()
        self._lock = threading.Lock()
        self._workers = [
            threading.Thread(
                target=self._worker,
                name=f"videocenter-download-{index + 1}",
                daemon=True,
            )
            for index in range(worker_count)
        ]
        for worker in self._workers:
            worker.start()

    def enqueue(self, task_id: int) -> bool:
        with self._lock:
            if task_id in self._tokens:
                return False
            self._tokens[task_id] = DownloadCancellationToken()
        self._queue.put(task_id)
        return True

    def cancel(self, task_id: int) -> bool:
        with self._lock:
            token = self._tokens.get(task_id)
        if token is None:
            return False
        token.cancel()
        return True

    def pause(self, task_id: int) -> bool:
        with self._lock:
            token = self._tokens.get(task_id)
        if token is None:
            return False
        token.pause()
        return True

    def resume(self, task_id: int) -> bool:
        with self._lock:
            token = self._tokens.get(task_id)
        if token is None:
            return False
        token.resume()
        return True

    def contains(self, task_id: int) -> bool:
        with self._lock:
            return task_id in self._tokens

    def is_running(self, task_id: int) -> bool:
        with self._lock:
            return task_id in self._running_ids

    @property
    def waiting_count(self) -> int:
        return self._queue.qsize()

    @property
    def running_count(self) -> int:
        with self._lock:
            return len(self._running_ids)

    def join(self) -> None:
        self._queue.join()

    def shutdown(self) -> None:
        for _ in self._workers:
            self._queue.put(None)
        for worker in self._workers:
            worker.join(timeout=5)

    def _worker(self) -> None:
        while True:
            task_id = self._queue.get()
            try:
                if task_id is None:
                    return
                with self._lock:
                    token = self._tokens[task_id]
                    self._running_ids.add(task_id)
                if not token.is_cancelled:
                    token.wait_if_paused()
                    self._runner(task_id, token)
            finally:
                if task_id is not None:
                    with self._lock:
                        self._running_ids.discard(task_id)
                        self._tokens.pop(task_id, None)
                self._queue.task_done()
