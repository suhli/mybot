from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable


TaskFunc = Callable[[], None]


@dataclass(slots=True)
class _TaskEntry:
    name: str
    func: TaskFunc
    interval_seconds: int
    run_on_start: bool
    next_run_ts: float


class TaskScheduler:
    def __init__(self, tick_seconds: float = 1.0) -> None:
        self._tick_seconds = tick_seconds
        self._tasks: list[_TaskEntry] = []
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def register_interval_task(
        self,
        *,
        name: str,
        func: TaskFunc,
        interval_seconds: int,
        run_on_start: bool = True,
    ) -> None:
        if not name:
            raise ValueError("task name must not be empty")
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be > 0")

        now = time.time()
        entry = _TaskEntry(
            name=name,
            func=func,
            interval_seconds=interval_seconds,
            run_on_start=run_on_start,
            next_run_ts=now if run_on_start else now + interval_seconds,
        )
        with self._lock:
            self._tasks.append(entry)

    def start(self) -> None:
        if self._thread.is_alive():
            return
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            now = time.time()
            with self._lock:
                tasks = list(self._tasks)

            for task in tasks:
                if now < task.next_run_ts:
                    continue

                try:
                    task.func()
                except Exception as exc:  # noqa: BLE001
                    print(f"[TaskScheduler][{task.name}] 执行失败: {exc}")
                finally:
                    task.next_run_ts = now + task.interval_seconds

            time.sleep(self._tick_seconds)

