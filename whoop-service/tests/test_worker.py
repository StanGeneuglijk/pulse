"""Integration tests that exercise a real RQ worker draining a real batch
— every other test calls sync_one_user() directly, bypassing
enqueue/dequeue/failure-isolation entirely. Always run as a batch of more
than one job: a single-job run would never catch one user's failure
affecting another's, which is the actual production shape (`/sync/batch`
fans out to every connected user at once). The worker mechanics
themselves (fork/thread/signal safety) live in tests/support.py's
WorkerHarness — this class only ever calls harness.enqueue/run_burst/status.
"""

import runpy
import uuid
from unittest.mock import patch

import respx
from rq import Retry, Worker
from sqlalchemy import select

from services.whoop import crud
from services.whoop.models import Recovery, SyncJobLog, User
from tests.support import mock_whoop


class TestWorkerIntegration:
    @respx.mock
    async def test_happy_path_a_batch_of_healthy_jobs_all_complete(
        self, db_session, connected_user, worker_harness
    ):
        """Scope: the ordinary case — every job in the batch belongs to a
        genuinely connected user and succeeds. Two users, not one, so
        this still proves jobs are handled independently rather than
        only proving a single job can run. Exercises RQ's real
        dequeue/serialization path (enqueue -> SimpleWorker ->
        sync_one_user), not a direct call to sync_one_user, which every
        other test in this suite uses."""
        other_user = User(id=uuid.uuid4(), whoop_connected=True)
        db_session.add(other_user)
        await db_session.commit()

        mock_whoop(
            recovery=[
                {
                    "cycle_id": 1,
                    "score": {"recovery_score": 70},
                    "created_at": "2026-07-22T00:00:00Z",
                }
            ]
        )

        connected_job = worker_harness.enqueue(str(connected_user.id))

        await worker_harness.run_burst()

        assert worker_harness.status(connected_job) == "finished"
        rows = await db_session.execute(
            select(Recovery).where(Recovery.user_id == connected_user.id)
        )
        assert len(rows.scalars().all()) == 1

    @respx.mock
    async def test_edge_case_failing_jobs_in_a_batch_never_block_a_healthy_one(
        self, db_session, connected_user, worker_harness
    ):
        """Scope: two different, realistic failure modes landing in the
        same batch as a healthy job — a user row that exists but was
        never actually connected (no tokens, MissingCredentialError) and
        a user_id that doesn't exist in the database at all
        (UserNotFoundError). Proves job_queue.md's failure-isolation
        claim: neither failure prevents the healthy job in the same
        batch from completing and persisting its data."""
        mock_whoop()
        never_connected_user = User(id=uuid.uuid4(), whoop_connected=True)
        db_session.add(never_connected_user)
        await db_session.commit()

        missing_user_id = str(uuid.uuid4())
        job_ids = {
            "healthy": worker_harness.enqueue(str(connected_user.id)),
            "missing_credentials": worker_harness.enqueue(str(never_connected_user.id)),
            "user_not_found": worker_harness.enqueue(missing_user_id),
        }

        await worker_harness.run_burst()

        assert worker_harness.status(job_ids["healthy"]) == "finished"
        assert worker_harness.status(job_ids["missing_credentials"]) == "failed"
        assert worker_harness.status(job_ids["user_not_found"]) == "failed"

    @respx.mock
    async def test_happy_path_a_job_retries_after_a_transient_failure_and_then_succeeds(
        self, db_session, connected_user, worker_harness, monkeypatch
    ):
        """Scope: SYNC_JOB_RETRY_MAX/_INTERVALS_SECONDS are configured
        but otherwise never exercised by any test — this proves a job
        that fails once genuinely gets a second attempt (not just
        correctly reported as failed) and that the second attempt's
        success is what actually lands in the database. interval=[0]
        keeps the test fast; the real intervals are core/config.py's
        concern, not this mechanism's."""
        mock_whoop(
            recovery=[
                {
                    "cycle_id": 1,
                    "score": {"recovery_score": 70},
                    "created_at": "2026-07-22T00:00:00Z",
                }
            ]
        )
        real_get_user = crud.get_user
        calls = {"n": 0}

        async def flaky_get_user(db, user_id):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("simulated transient failure")
            return await real_get_user(db, user_id)

        monkeypatch.setattr(crud, "get_user", flaky_get_user)

        job_id = worker_harness.enqueue(
            str(connected_user.id),
            trigger_source="cron",
            retry=Retry(max=1),
        )
        await worker_harness.run_burst()

        assert calls["n"] == 2  # the first attempt failed; the retry is what succeeded
        assert worker_harness.status(job_id) == "finished"
        rows = await db_session.execute(
            select(Recovery).where(Recovery.user_id == connected_user.id)
        )
        assert len(rows.scalars().all()) == 1

        # Both attempts are real, durable rows sharing one job_id — not
        # just a final status number, an actual per-attempt history.
        log_rows = (
            (
                await db_session.execute(
                    select(SyncJobLog)
                    .where(SyncJobLog.job_id == job_id)
                    .order_by(SyncJobLog.attempt_number)
                )
            )
            .scalars()
            .all()
        )
        assert [row.attempt_number for row in log_rows] == [1, 2]
        assert [row.status for row in log_rows] == ["failed", "success"]
        assert all(row.trigger_source == "cron" for row in log_rows)

    async def test_edge_case_a_job_that_always_fails_exhausts_its_retries_then_fails(
        self, worker_harness, monkeypatch
    ):
        """Scope: the other half of the same mechanism — a job whose
        failure isn't transient must still retry exactly `max` times
        (proving RQ's retry loop actually ran, not that it merely failed
        once), then stop and report as failed rather than retrying
        forever."""
        calls = {"n": 0}

        async def always_failing_get_user(db, user_id):
            calls["n"] += 1
            raise RuntimeError("simulated permanent failure")

        monkeypatch.setattr(crud, "get_user", always_failing_get_user)

        job_id = worker_harness.enqueue(str(uuid.uuid4()), retry=Retry(max=1))
        await worker_harness.run_burst()

        assert calls["n"] == 2  # the original attempt plus exactly one retry
        assert worker_harness.status(job_id) == "failed"

    def test_worker_entrypoint_runs_without_the_rq_scheduler(self):
        """Scope: regression for the Oct 2026 Redis-quota outage. RQ's scheduler polls Redis every
        second, around 345K commands a day, which exhausts Upstash's free
        500K-a-month quota within two days and takes the sync down. The
        worker entrypoint must never start it."""
        with patch.object(Worker, "work") as work:
            runpy.run_module("workers.run", run_name="__main__")

        work.assert_called_once()
        assert not work.call_args.kwargs.get("with_scheduler", False)
