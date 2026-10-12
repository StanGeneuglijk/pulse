"""Test infrastructure with no pytest-specific magic — plain functions and
classes, wired into fixtures by conftest.py. Mirrors the app's own split:
this module is the "core" layer every test class builds on, never the
other way around.
"""

import asyncio

import respx
from httpx import Response
from rq import Retry, SimpleWorker
from rq.timeouts import TimerDeathPenalty

from core.queue import redis_conn
from services.whoop.config import SYNC_JOB_TIMEOUT_SECONDS, sync_queue


def mock_whoop(
    *,
    recovery: list | None = None,
    sleep: list | None = None,
    workout: list | None = None,
    cycle: list | None = None,
    body: dict | None = None,
) -> None:
    """Mock WHOOP's data endpoints for a test decorated with @respx.mock.
    Each list kwarg is raw records as WHOOP returns them; omitted ones are
    empty. Recovery is registered first (tests index `respx.routes[0]`)."""
    respx.get(url__regex=r".*/v2/recovery").mock(
        return_value=Response(200, json={"records": recovery or []})
    )
    respx.get(url__regex=r".*/v2/activity/sleep").mock(
        return_value=Response(200, json={"records": sleep or []})
    )
    respx.get(url__regex=r".*/v2/activity/workout").mock(
        return_value=Response(200, json={"records": workout or []})
    )
    respx.get(url__regex=r".*/v2/cycle").mock(
        return_value=Response(200, json={"records": cycle or []})
    )
    respx.get(url__regex=r".*/v2/user/measurement/body").mock(
        return_value=Response(200, json=body or {})
    )


class WorkerHarness:
    """Runs a real RQ worker against the real queue in tests. Single
    purpose: hide the macOS/thread-safety mechanics (SimpleWorker's fork
    avoidance, off-thread burst runs, thread-safe timeout enforcement)
    behind enqueue/run/status — no test should need to know any of that
    to use a real worker.
    """

    def __init__(self) -> None:
        self._worker = SimpleWorker([sync_queue], connection=redis_conn)
        # Signal-based mechanics only work in a process's main thread;
        # run_burst() runs off-thread (see below), so both are swapped
        # for thread-safe equivalents.
        self._worker._install_signal_handlers = lambda: None  # type: ignore[method-assign]
        self._worker.death_penalty_class = TimerDeathPenalty

    def enqueue(
        self,
        user_id: str,
        *,
        trigger_source: str = "manual",
        request_id: str | None = None,
        retry: Retry | None = None,
    ) -> str:
        job = sync_queue.enqueue(
            "services.whoop.sync.sync_one_user",
            user_id,
            trigger_source,
            request_id,
            job_timeout=SYNC_JOB_TIMEOUT_SECONDS,
            retry=retry,
        )
        return job.id

    async def run_burst(self) -> None:
        # RQ's job execution calls loop.run_until_complete() internally
        # (sync_one_user is a coroutine) — off-thread avoids colliding
        # with the loop an `async def` test already runs inside.
        await asyncio.to_thread(self._worker.work, burst=True)

    @staticmethod
    def status(job_id: str) -> str:
        job = sync_queue.fetch_job(job_id)
        assert job is not None
        return job.get_status()
