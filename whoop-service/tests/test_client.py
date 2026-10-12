import asyncio
from datetime import datetime

import httpx
import pytest
import respx
from pydantic import ValidationError

from services.whoop import circuit_breaker, client
from services.whoop.config import WHOOP_CIRCUIT_THRESHOLD
from services.whoop.exceptions import WhoopDegradedError
from services.whoop.whoop_types import RecoveryRecord, SleepRecord, WorkoutRecord
from tests.support import mock_whoop

_CREATED_AT = "2026-07-22T00:00:00Z"


class TestFetchAll:
    """The trust boundary — WHOOP's raw JSON responses parsed into typed
    models right here, so a shape change fails loudly at this one point
    instead of silently three layers downstream."""

    @respx.mock
    async def test_happy_path_returns_all_three_datasets(self):
        mock_whoop(
            recovery=[{"cycle_id": 1, "created_at": _CREATED_AT}],
            sleep=[{"id": "s1", "created_at": _CREATED_AT}],
            workout=[{"id": "w1", "created_at": _CREATED_AT}],
        )

        data = await client.fetch_all("fake-token")

        assert data.recoveries == [RecoveryRecord(cycle_id=1, created_at=_CREATED_AT)]
        assert data.sleep == [SleepRecord(id="s1", created_at=_CREATED_AT)]
        assert data.workouts == [WorkoutRecord(id="w1", created_at=_CREATED_AT)]

    @respx.mock
    async def test_happy_path_follows_next_token_across_pages(self):
        """Scope: WHOOP paginates collections — a sync must read every page,
        not just the first."""
        route = respx.get(url__regex=r".*/v2/recovery")
        route.side_effect = [
            httpx.Response(
                200,
                json={"records": [{"cycle_id": 1, "created_at": _CREATED_AT}], "next_token": "p2"},
            ),
            httpx.Response(200, json={"records": [{"cycle_id": 2, "created_at": _CREATED_AT}]}),
        ]
        respx.get(url__regex=r".*/v2/(activity/sleep|activity/workout|cycle|user/.*)").mock(
            return_value=httpx.Response(200, json={"records": []})
        )

        data = await client.fetch_all("fake-token")

        assert [r.cycle_id for r in data.recoveries] == [1, 2]
        assert route.calls[1].request.url.params["nextToken"] == "p2"

    @respx.mock
    async def test_edge_case_since_is_sent_as_the_start_filter(self):
        route = respx.get(url__regex=r".*/v2/recovery").mock(
            return_value=httpx.Response(200, json={"records": []})
        )
        respx.get(url__regex=r".*/v2/(activity/sleep|activity/workout|cycle|user/.*)").mock(
            return_value=httpx.Response(200, json={"records": []})
        )

        await client.fetch_all("fake-token", datetime(2026, 9, 1, 12, 0))

        assert route.calls[0].request.url.params["start"] == "2026-09-01T12:00:00.000Z"

    @respx.mock
    async def test_edge_case_cycles_and_body_are_skipped_when_the_scope_is_missing(self):
        """Scope: tokens granted before read:cycles/read:body_measurement were
        requested still sync everything else."""
        respx.get(url__regex=r".*/v2/(recovery|activity/sleep|activity/workout)").mock(
            return_value=httpx.Response(200, json={"records": []})
        )
        respx.get(url__regex=r".*/v2/(cycle|user/measurement/body)").mock(
            return_value=httpx.Response(401)
        )

        data = await client.fetch_all("fake-token")

        assert data.cycles == []
        assert data.body is None

    async def test_edge_case_refuses_to_fetch_while_the_circuit_is_open(self):
        """Scope: an open circuit must short-circuit before any network
        call, not after one fails — proves fetch_all actually consults
        the breaker, not just that the breaker module works in isolation
        (see test_circuit_breaker.py for that)."""
        for _ in range(WHOOP_CIRCUIT_THRESHOLD):
            await circuit_breaker.record_failure()
        try:
            with pytest.raises(WhoopDegradedError):
                await client.fetch_all("fake-token")  # no respx mock registered at all
        finally:
            await circuit_breaker.record_success()

    @respx.mock
    async def test_edge_case_raises_loudly_on_a_shape_change(self):
        """Scope: if WHOOP ever renames or drops a required field, this
        must fail here — at the trust boundary — not as a
        silently-wrong None three layers downstream in crud.py."""
        mock_whoop(recovery=[{"cycle_id": 1}])  # missing created_at

        with pytest.raises(ValidationError):
            await client.fetch_all("fake-token")

    async def test_edge_case_never_exceeds_configured_concurrency(self, monkeypatch):
        """Scope: proves the Semaphore actually bounds in-flight
        requests, not just that three responses eventually come back.
        Patches settings to a limit of 1 and tracks the high-water mark
        of concurrent calls into _get."""
        monkeypatch.setattr(client.whoop_settings, "whoop_fetch_concurrency", 1)

        in_flight = 0
        max_in_flight = 0
        lock = asyncio.Lock()

        async def fake_get(http_client, sem, path, token, params):
            nonlocal in_flight, max_in_flight
            async with sem:
                async with lock:
                    in_flight += 1
                    max_in_flight = max(max_in_flight, in_flight)
                await asyncio.sleep(0.05)  # hold the semaphore long enough to overlap if unbounded
                async with lock:
                    in_flight -= 1
                return {"records": []}

        monkeypatch.setattr(client, "_get_page", fake_get)

        await client.fetch_all("fake-token")

        assert max_in_flight == 1  # never more than whoop_fetch_concurrency at once


class TestGetWithRetry:
    """Retry/backoff against WHOOP itself — distinct from RQ's job-level
    Retry (see test_worker.py), this is the client.py-level retry for a
    single HTTP call."""

    async def test_happy_path_succeeds_after_one_retryable_failure(self, monkeypatch):
        """Scope: a 429 followed by a 200 should succeed after exactly
        one retry — proves RETRYABLE_STATUSES are actually retried, not
        just tolerated by luck."""
        monkeypatch.setattr(asyncio, "sleep", self._no_op_sleep)  # skip the real backoff delay

        calls = {"n": 0}

        async def fake_get(http_client, sem, path, token, params):
            calls["n"] += 1
            if calls["n"] == 1:
                request = httpx.Request("GET", "https://api.prod.whoop.com/developer/v2/recovery")
                raise httpx.HTTPStatusError(
                    "rate limited", request=request, response=httpx.Response(429, request=request)
                )
            return {"records": [{"cycle_id": 1}]}

        monkeypatch.setattr(client, "_get_page", fake_get)

        sem = asyncio.Semaphore(1)
        async with httpx.AsyncClient() as http_client:
            result = await client._get_page_with_retry(
                http_client, sem, "/v2/recovery", "fake-token", {}
            )

        assert result == {"records": [{"cycle_id": 1}]}
        assert calls["n"] == 2  # one failure, one successful retry

    async def test_edge_case_raises_immediately_on_401(self, monkeypatch):
        """Scope: a 401 (expired/invalid token) must not be retried — it
        will fail identically every time, so retrying only wastes time."""
        calls = {"n": 0}

        async def fake_get(http_client, sem, path, token, params):
            calls["n"] += 1
            request = httpx.Request("GET", "https://api.prod.whoop.com/developer/v2/recovery")
            raise httpx.HTTPStatusError(
                "unauthorized", request=request, response=httpx.Response(401, request=request)
            )

        monkeypatch.setattr(client, "_get_page", fake_get)

        sem = asyncio.Semaphore(1)
        async with httpx.AsyncClient() as http_client:
            with pytest.raises(httpx.HTTPStatusError):
                await client._get_page_with_retry(
                    http_client, sem, "/v2/recovery", "fake-token", {}
                )

        assert calls["n"] == 1  # zero retries — raised on the first attempt

    @staticmethod
    async def _no_op_sleep(_seconds: float) -> None:
        return None
