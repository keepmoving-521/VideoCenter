import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from threading import Lock

from videocenter.models.background_task import (
    BackgroundTask,
    BackgroundTaskStatus,
    BackgroundTaskType,
)

SUBSCRIBER_QUEUE_SIZE = 100


@dataclass(eq=False, slots=True)
class TaskEventSubscriber:
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[dict]
    task_type: BackgroundTaskType | None
    status: BackgroundTaskStatus | None


class TaskEventBroker:
    def __init__(self) -> None:
        self._subscribers: set[TaskEventSubscriber] = set()
        self._lock = Lock()

    @asynccontextmanager
    async def subscribe(
        self,
        *,
        task_type: BackgroundTaskType | None = None,
        status: BackgroundTaskStatus | None = None,
    ) -> AsyncIterator[asyncio.Queue[dict]]:
        subscriber = TaskEventSubscriber(
            loop=asyncio.get_running_loop(),
            queue=asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_SIZE),
            task_type=task_type,
            status=status,
        )
        with self._lock:
            self._subscribers.add(subscriber)
        try:
            yield subscriber.queue
        finally:
            with self._lock:
                self._subscribers.discard(subscriber)

    def publish(
        self,
        task: BackgroundTask,
        *,
        event: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        payload = _task_event_payload(
            task,
            event=event,
            message=message,
            details=details or {},
        )
        with self._lock:
            subscribers = tuple(self._subscribers)
        for subscriber in subscribers:
            if subscriber.task_type is not None and subscriber.task_type != task.task_type:
                continue
            if subscriber.status is not None and subscriber.status != task.status:
                continue
            try:
                subscriber.loop.call_soon_threadsafe(
                    self._enqueue_latest,
                    subscriber,
                    payload,
                )
            except RuntimeError:
                with self._lock:
                    self._subscribers.discard(subscriber)

    @staticmethod
    def _enqueue_latest(
        subscriber: TaskEventSubscriber,
        payload: dict,
    ) -> None:
        if subscriber.queue.full():
            try:
                subscriber.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        subscriber.queue.put_nowait(payload)


def _task_event_payload(
    task: BackgroundTask,
    *,
    event: str,
    message: str,
    details: dict,
) -> dict:
    return {
        "type": "task_event",
        "event": event,
        "message": message,
        "details": details,
        "occurred_at": datetime.now().isoformat(),
        "task": {
            "id": task.id,
            "task_type": task.task_type.value,
            "status": task.status.value,
            "title": task.title,
            "source_task_id": task.source_task_id,
            "parent_task_id": task.parent_task_id,
            "priority": task.priority,
            "progress": task.progress,
            "processed_items": task.processed_items,
            "total_items": task.total_items,
            "attempt": task.attempt,
            "max_attempts": task.max_attempts,
            "cancellable": task.cancellable,
            "pause_supported": task.pause_supported,
            "cancel_requested": task.cancel_requested,
            "worker_id": task.worker_id,
            "task_result": task.task_result,
            "error_code": task.error_code,
            "error_message": task.error_message,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "heartbeat_at": task.heartbeat_at.isoformat() if task.heartbeat_at else None,
        },
    }


task_event_broker = TaskEventBroker()
