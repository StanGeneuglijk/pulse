import uuid
from datetime import timedelta

from httpx import ASGITransport, AsyncClient

from api.main import app
from core.clock import utcnow
from services.whoop.config import sync_queue
from services.whoop.models import SyncJobLog, User, UserActivityLog


class TestUserSync:
    """POST /users/{user_id}/sync — the manual "refresh from WHOOP"
    trigger a dashboard offers, distinct from callback()'s automatic
    login-time sync and sync_batch's operator-level fan-out."""

    def setup_method(self) -> None:
        sync_queue.empty()

    def teardown_method(self) -> None:
        sync_queue.empty()

    async def test_happy_path_enqueues_a_job_for_that_user(self, client, connected_user):
        response = await client.post(f"/users/{connected_user.id}/sync")

        assert response.status_code == 202
        assert response.json() == {"queued": True}
        assert sync_queue.count == 1

    async def test_edge_case_a_repeat_within_the_debounce_window_queues_nothing(
        self, client, connected_user
    ):
        await client.post(f"/users/{connected_user.id}/sync")
        response = await client.post(f"/users/{connected_user.id}/sync")

        assert response.status_code == 202
        assert response.json() == {"queued": False}
        assert sync_queue.count == 1

    async def test_edge_case_rejects_a_call_with_no_api_key(self, anonymous_client, connected_user):
        response = await anonymous_client.post(f"/users/{connected_user.id}/sync")

        assert response.status_code == 401
        assert sync_queue.count == 0

    async def test_edge_case_a_users_read_token_cannot_trigger_another_users_sync(
        self, db_session, connected_user
    ):
        """Scope: same cross-user isolation the read routes already
        enforce, applied to the write side — a read_token must not be
        able to force a sync for someone else's account."""
        other_user = User(id=uuid.uuid4(), whoop_connected=True, read_token="other-users-token")
        db_session.add(other_user)
        await db_session.commit()

        transport = ASGITransport(app=app)
        headers = {"Authorization": f"Bearer {connected_user.read_token}"}
        async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
            response = await ac.post(f"/users/{other_user.id}/sync")

        assert response.status_code == 401
        assert sync_queue.count == 0


class TestUserLogs:
    """GET /users/{user_id}/activity and /syncs — a user's own dashboard
    view of their behavioral and operational history. Each row's
    created_at is set explicitly, not left to the model's own utcnow()
    default — two rows written in the same commit could otherwise land
    on the same microsecond and make the most-recent-first ordering
    these tests assert on flaky."""

    _NOW = utcnow()

    async def test_happy_path_activity_returns_this_users_rows_most_recent_first(
        self, client, db_session, connected_user
    ):
        db_session.add(
            UserActivityLog(user_id=connected_user.id, route="recovery", created_at=self._NOW)
        )
        db_session.add(
            UserActivityLog(
                user_id=connected_user.id,
                route="sleep",
                created_at=self._NOW + timedelta(seconds=1),
            )
        )
        await db_session.commit()

        response = await client.get(f"/users/{connected_user.id}/activity")

        assert response.status_code == 200
        routes = [row["route"] for row in response.json()]
        assert routes == ["sleep", "recovery"]  # most recent first

    async def test_edge_case_activity_excludes_another_users_rows(
        self, client, db_session, connected_user
    ):
        other_user_id = uuid.uuid4()
        db_session.add(User(id=other_user_id, whoop_connected=False))
        db_session.add(UserActivityLog(user_id=connected_user.id, route="recovery"))
        db_session.add(UserActivityLog(user_id=other_user_id, route="workout"))
        await db_session.commit()

        response = await client.get(f"/users/{connected_user.id}/activity")

        assert [row["route"] for row in response.json()] == ["recovery"]

    async def test_happy_path_syncs_returns_this_users_rows_most_recent_first(
        self, client, db_session, connected_user
    ):
        db_session.add(
            SyncJobLog(
                user_id=connected_user.id,
                created_at=self._NOW,
                attempt_number=1,
                trigger_source="login",
                status="success",
                retries_left=None,
                recoveries_synced=1,
                sleep_synced=1,
                workouts_synced=0,
                duration_ms=120.0,
                error_message=None,
            )
        )
        db_session.add(
            SyncJobLog(
                user_id=connected_user.id,
                created_at=self._NOW + timedelta(seconds=1),
                attempt_number=1,
                trigger_source="manual",
                status="failed",
                retries_left=None,
                recoveries_synced=0,
                sleep_synced=0,
                workouts_synced=0,
                duration_ms=50.0,
                error_message="WHOOP unreachable",
            )
        )
        await db_session.commit()

        response = await client.get(f"/users/{connected_user.id}/syncs")

        assert response.status_code == 200
        body = response.json()
        assert [row["triggerSource"] for row in body] == ["manual", "login"]  # most recent first
        assert body[0]["status"] == "failed"
        assert body[0]["errorMessage"] == "WHOOP unreachable"
