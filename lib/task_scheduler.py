from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Sequence


TaskFunc = Callable[[], None]

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _TaskEntry:
    name: str
    func: TaskFunc
    interval_seconds: int
    run_on_start: bool
    next_run_ts: float
    next_run_ts_factory: Callable[[float], float]


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
            next_run_ts_factory=lambda current_ts: current_ts + interval_seconds,
        )
        with self._lock:
            self._tasks.append(entry)

    def register_daily_task(
        self,
        *,
        name: str,
        func: TaskFunc,
        hour: int | None = None,
        minute: int = 0,
        second: int = 0,
        times: Sequence[tuple[int, int, int]] | None = None,
        run_on_start: bool = False,
    ) -> None:
        if not name:
            raise ValueError("task name must not be empty")
        if hour is None and not times:
            raise ValueError("hour or times must be provided")
        if hour is not None and times:
            raise ValueError("cannot provide both hour and times")

        daily_times: tuple[tuple[int, int, int], ...]
        if times:
            normalized = []
            for value in times:
                if len(value) != 3:
                    raise ValueError("each item in times must be (hour, minute, second)")
                h, m, s = value
                self._validate_daily_time(h, m, s)
                normalized.append((h, m, s))
            daily_times = tuple(sorted(set(normalized)))
        else:
            self._validate_daily_time(hour, minute, second)
            daily_times = ((hour, minute, second),)

        now = time.time()
        entry = _TaskEntry(
            name=name,
            func=func,
            interval_seconds=24 * 60 * 60,
            run_on_start=run_on_start,
            next_run_ts=now if run_on_start else self._next_daily_run_ts_for_times(daily_times, now),
            next_run_ts_factory=lambda current_ts: self._next_daily_run_ts_for_times(daily_times, current_ts),
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
                    logger.exception("任务 %s 执行失败", task.name)
                finally:
                    task.next_run_ts = task.next_run_ts_factory(now)

            time.sleep(self._tick_seconds)

    @staticmethod
    def _validate_daily_time(hour: int, minute: int, second: int) -> None:
        if not 0 <= hour <= 23:
            raise ValueError("hour must be in [0, 23]")
        if not 0 <= minute <= 59:
            raise ValueError("minute must be in [0, 59]")
        if not 0 <= second <= 59:
            raise ValueError("second must be in [0, 59]")

    @staticmethod
    def _next_daily_run_ts(hour: int, minute: int, second: int, now_ts: float) -> float:
        now_dt = datetime.fromtimestamp(now_ts)
        next_dt = now_dt.replace(hour=hour, minute=minute, second=second, microsecond=0)
        if next_dt <= now_dt:
            next_dt += timedelta(days=1)
        return next_dt.timestamp()

    @staticmethod
    def _next_daily_run_ts_for_times(times: tuple[tuple[int, int, int], ...], now_ts: float) -> float:
        return min(TaskScheduler._next_daily_run_ts(h, m, s, now_ts) for h, m, s in times)

