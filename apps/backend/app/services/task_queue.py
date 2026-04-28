"""Centralized GPU task queue.

Single-worker ThreadPoolExecutor ensures only one GPU-bound job runs at a time.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("fedarena.task_queue")

_queue: TaskQueue | None = None


@dataclass
class QueuedTask:
    key: str
    job_type: str
    future: Future[Any]
    cancel_event: threading.Event
    on_cancel: Callable[[], None] | None = None


class TaskQueue:
    def __init__(self, max_workers: int = 1):
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="gpu-worker")
        self._tasks: dict[str, QueuedTask] = {}
        self._lock = threading.Lock()

    def submit(
        self,
        key: str,
        job_type: str,
        fn: Callable[..., Any],
        *args: Any,
        on_cancel: Callable[[], None] | None = None,
    ) -> QueuedTask:
        cancel_event = threading.Event()
        future = self._executor.submit(fn, *args, cancel_event)
        task = QueuedTask(
            key=key,
            job_type=job_type,
            future=future,
            cancel_event=cancel_event,
            on_cancel=on_cancel,
        )
        with self._lock:
            self._tasks[key] = task
        future.add_done_callback(lambda _: self._cleanup(key))
        return task

    def cancel(self, key: str) -> bool:
        with self._lock:
            task = self._tasks.get(key)
        if not task:
            return False
        task.cancel_event.set()
        cancelled = task.future.cancel()
        if cancelled and task.on_cancel:
            task.on_cancel()
        return True

    def status(self) -> dict[str, Any]:
        with self._lock:
            tasks = list(self._tasks.values())
        return {
            "total": len(tasks),
            "running": sum(1 for t in tasks if t.future.running()),
            "pending": sum(1 for t in tasks if not t.future.done() and not t.future.running()),
            "tasks": [
                {
                    "key": t.key,
                    "job_type": t.job_type,
                    "running": t.future.running(),
                    "done": t.future.done(),
                }
                for t in tasks
            ],
        }

    def pending_count(self) -> int:
        with self._lock:
            return sum(1 for t in self._tasks.values() if not t.future.done() and not t.future.running())

    def shutdown(self, wait: bool = True, cancel_pending: bool = False) -> None:
        if cancel_pending:
            with self._lock:
                tasks = list(self._tasks.values())
            for task in tasks:
                task.cancel_event.set()
                task.future.cancel()
        self._executor.shutdown(wait=wait)

    def _cleanup(self, key: str) -> None:
        with self._lock:
            self._tasks.pop(key, None)


def init_queue(max_workers: int = 1) -> None:
    global _queue
    _queue = TaskQueue(max_workers=max_workers)


def get_queue() -> TaskQueue:
    if _queue is None:
        raise RuntimeError("Task queue not initialized. Call init_queue() first.")
    return _queue


def shutdown_queue() -> None:
    global _queue
    if _queue is not None:
        _queue.shutdown(wait=True, cancel_pending=True)
        _queue = None
