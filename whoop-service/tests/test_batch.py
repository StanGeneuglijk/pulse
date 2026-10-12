from datetime import timedelta

import pytest_asyncio

from core.clock import utcnow
from core.crypto import encrypt_token
from core.queue import redis_conn
from services.whoop.config import BATCH_LOCK_KEY, SYNC_JOB_RETRY_MAX, sync_queue
from services.whoop.models import User


class TestSyncBatch:
    @pytest_asyncio.fixture(autouse=True)
    def _clean_batch_state(self):
        """/sync/batch's debounce lock is a separate concern from the
        queue worker_harness cleans up elsewhere — this class hits the
        real HTTP route, never a real worker, so it owns its own cleanup."""
        sync_queue.empty()
        redis_conn.delete(BATCH_LOCK_KEY)
        yield
        sync_queue.empty()
        redis_conn.delete(BATCH_LOCK_KEY)

    @staticmethod
    async def _make_user(db_session, *, connected: bool) -> User:
        from core.config import settings

        user = User(
            encrypted_access_token=encrypt_token("fake-access", settings.token_encryption_key)
            if connected
            else None,
            encrypted_refresh_token=encrypt_token("fake-refresh", settings.token_encryption_key)
            if connected
            else None,
            token_expires_at=utcnow() + timedelta(hours=1) if connected else None,
            whoop_connected=connected,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    async def test_happy_path_enqueues_one_job_per_connected_user(self, client, db_session):
        """Scope: the ordinary case — a mix of connected and
        non-connected users, only the connected ones get enqueued. The
        core /sync/batch contract this whole route exists for."""
        await self._make_user(db_session, connected=True)
        await self._make_user(db_session, connected=True)
        await self._make_user(db_session, connected=False)  # excluded — not whoop_connected

        response = await client.post("/sync/batch")

        assert response.status_code == 202
        assert response.json() == {"queued": 2}
        assert sync_queue.count == 2

    async def test_batch_jobs_retry_immediately(self, client, db_session):
        """Scope: regression for the Oct 2026 Redis-quota outage. A retry with a delay sits in RQ's
        scheduled registry until a scheduler moves it, and the worker runs
        no scheduler (it exhausted Upstash's free quota). Every queued job
        must therefore retry with no delay, or its retries would never run."""
        await self._make_user(db_session, connected=True)
        await self._make_user(db_session, connected=True)

        response = await client.post("/sync/batch")

        assert response.status_code == 202
        jobs = sync_queue.get_jobs()
        assert len(jobs) == 2
        for job in jobs:
            assert job.retries_left == SYNC_JOB_RETRY_MAX
            assert all(interval == 0 for interval in job.retry_intervals or [0])

    async def test_edge_case_with_zero_connected_users_queues_nothing(self, client, db_session):
        """Scope: no connected users at all — must still respond cleanly
        (202, queued: 0), not error, and must not acquire the debounce
        lock for no reason (a follow-up call with a real user shouldn't
        be blocked by an empty run)."""
        await self._make_user(db_session, connected=False)

        response = await client.post("/sync/batch")

        assert response.status_code == 202
        assert response.json() == {"queued": 0}
        assert sync_queue.count == 0

    async def test_happy_path_returns_immediately_without_calling_whoop(self, client, db_session):
        """Scope: no WHOOP calls happen as part of handling /sync/batch —
        enqueueing only writes to Redis. If this test needed network
        access to pass, that would itself be the bug (see
        building_plan.md Milestone 6)."""
        await self._make_user(db_session, connected=True)

        response = await client.post("/sync/batch")

        assert response.status_code == 202
        assert response.json() == {"queued": 1}

    async def test_edge_case_rejects_a_second_call_within_the_cooldown(self, client, db_session):
        """Scope: the debounce lock — a second call inside the cooldown
        window must be rejected before it ever re-reads the
        connected-user list or enqueues anything a second time."""
        await self._make_user(db_session, connected=True)

        first = await client.post("/sync/batch")
        second = await client.post("/sync/batch")

        assert first.status_code == 202
        assert second.status_code == 429
        assert "Retry-After" in second.headers
        assert sync_queue.count == 1  # only the first call's job is queued

    async def test_edge_case_rejects_a_batch_over_the_safety_cap(
        self, client, db_session, monkeypatch
    ):
        """Scope: SYNC_BATCH_MAX_USERS — a connected-user count over the
        cap must be refused outright, not silently truncated (a
        truncated batch would leave some connected users never synced
        with no signal anything was dropped), and must not enqueue
        anything at all."""
        from services.whoop import router

        monkeypatch.setattr(router, "SYNC_BATCH_MAX_USERS", 2)
        await self._make_user(db_session, connected=True)
        await self._make_user(db_session, connected=True)
        await self._make_user(db_session, connected=True)

        response = await client.post("/sync/batch")

        assert response.status_code == 400
        assert "3" in response.json()["detail"]  # connected_count
        assert "2" in response.json()["detail"]  # max_allowed
        assert sync_queue.count == 0

    async def test_edge_case_rejects_a_call_with_no_api_key(self, anonymous_client, db_session):
        """Scope: caller authentication — an unauthenticated request must
        be rejected before it ever touches the connected-user list or the
        queue."""
        await self._make_user(db_session, connected=True)

        response = await anonymous_client.post("/sync/batch")

        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert sync_queue.count == 0  # rejected before the batch ever ran
