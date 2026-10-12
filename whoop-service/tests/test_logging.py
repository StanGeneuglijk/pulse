"""Proves rows actually land in the durable log tables (ErrorLog,
SyncJobLog, UserActivityLog), and that request ids correlate them."""

import uuid

import respx
from sqlalchemy import select

from core.log_models import ErrorLog
from services.whoop.models import SyncJobLog, UserActivityLog
from services.whoop.sync import sync_one_user
from tests.support import mock_whoop


class TestOperationalLogs:
    async def test_happy_path_every_response_carries_a_request_id(self, client):
        response = await client.get("/health")

        assert uuid.UUID(response.headers["X-Request-ID"])

    async def test_edge_case_a_domain_exception_writes_an_error_log_row(
        self, anonymous_client, db_session
    ):
        await anonymous_client.get("/auth/callback", params={"code": "x", "state": "bogus"})

        rows = await db_session.execute(
            select(ErrorLog).where(ErrorLog.exception_type == "InvalidOAuthStateError")
        )
        row = rows.scalars().one()
        assert row.context == "/auth/callback"

    async def test_happy_path_an_error_logs_request_id_matches_its_causing_request(
        self, anonymous_client, db_session
    ):
        """Scope: the id returned as X-Request-ID is the one stored on the
        ErrorLog row that request caused."""
        response = await anonymous_client.get(
            "/auth/callback", params={"code": "x", "state": "still-bogus"}
        )

        error_row = (
            await db_session.execute(
                select(ErrorLog).where(ErrorLog.exception_type == "InvalidOAuthStateError")
            )
        ).scalars().one()

        assert str(error_row.request_id) == response.headers["X-Request-ID"]


class TestBehavioralLogs:
    async def test_happy_path_a_read_route_hit_writes_a_user_activity_log_row(
        self, client, db_session, connected_user
    ):
        await client.get(f"/users/{connected_user.id}/recovery")

        rows = await db_session.execute(
            select(UserActivityLog).where(UserActivityLog.user_id == connected_user.id)
        )
        row = rows.scalars().one()
        assert row.route == "recovery"

    @respx.mock
    async def test_happy_path_a_successful_sync_writes_a_sync_job_log_row(
        self, db_session, connected_user
    ):
        mock_whoop()

        await sync_one_user(str(connected_user.id), trigger_source="login")

        rows = await db_session.execute(
            select(SyncJobLog).where(SyncJobLog.user_id == connected_user.id)
        )
        row = rows.scalars().one()
        assert row.status == "success"
        assert row.trigger_source == "login"
        assert row.attempt_number == 1

    @respx.mock
    async def test_happy_path_sync_job_log_records_its_correlating_request_id(
        self, db_session, connected_user
    ):
        mock_whoop()
        request_id = uuid.uuid4()

        await sync_one_user(
            str(connected_user.id), trigger_source="login", request_id=str(request_id)
        )

        rows = await db_session.execute(
            select(SyncJobLog).where(SyncJobLog.user_id == connected_user.id)
        )
        row = rows.scalars().one()
        assert row.request_id == request_id

    async def test_edge_case_a_failed_sync_writes_a_sync_job_log_row_with_the_error(
        self, db_session
    ):
        missing_user_id = uuid.uuid4()

        try:
            await sync_one_user(str(missing_user_id), trigger_source="cron")
        except Exception:
            pass  # the failure itself is sync.py's own concern; this test is about the log row

        rows = await db_session.execute(
            select(SyncJobLog).where(SyncJobLog.user_id == missing_user_id)
        )
        row = rows.scalars().one()
        assert row.status == "failed"
        assert row.trigger_source == "cron"
        assert row.error_message is not None
