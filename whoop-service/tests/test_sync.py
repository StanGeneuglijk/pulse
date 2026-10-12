import pytest
import respx
from httpx import Response
from sqlalchemy import null, select, update

from core.clock import utcnow
from core.config import settings
from core.crypto import decrypt_token
from core.db import async_session_factory
from core.exceptions import UpstreamAuthError
from services.whoop import crud
from services.whoop.config import WHOOP_TOKEN_URL
from services.whoop.models import Recovery
from services.whoop.sync import sync_one_user
from tests.support import mock_whoop


class TestSyncOneUser:
    """Unit-level: sync_one_user() called directly, one input at a
    time — the batch/failure-isolation concerns belong to
    TestWorkerIntegration in test_worker.py, not here."""

    @respx.mock
    async def test_happy_path_is_idempotent(self, db_session, connected_user):
        """Scope: running the same sync twice must not duplicate rows —
        the upsert's whole reason to exist."""
        mock_whoop(
            recovery=[
                {
                    "cycle_id": 12345,
                    "score": {"recovery_score": 80},
                    "created_at": "2026-07-22T00:00:00Z",
                }
            ]
        )

        await sync_one_user(str(connected_user.id))
        await sync_one_user(str(connected_user.id))  # run twice on purpose

        rows = await db_session.execute(
            select(Recovery).where(Recovery.user_id == connected_user.id)
        )
        assert len(rows.scalars().all()) == 1

    @respx.mock
    async def test_happy_path_stores_every_metric_and_the_raw_record(
        self, db_session, connected_user
    ):
        mock_whoop(
            recovery=[
                {
                    "cycle_id": 7,
                    "sleep_id": "s1",
                    "created_at": "2026-09-01T07:00:00Z",
                    "score_state": "SCORED",
                    "score": {
                        "recovery_score": 72,
                        "resting_heart_rate": 48,
                        "hrv_rmssd_milli": 81.5,
                        "spo2_percentage": 97.1,
                        "skin_temp_celsius": 33.4,
                    },
                }
            ],
            sleep=[
                {
                    "id": "s1",
                    "cycle_id": 7,
                    "created_at": "2026-09-01T07:00:00Z",
                    "start": "2026-08-31T23:00:00Z",
                    "end": "2026-09-01T07:00:00Z",
                    "nap": False,
                    "score": {
                        "sleep_performance_percentage": 88,
                        "respiratory_rate": 14.2,
                        "stage_summary": {"total_rem_sleep_time_milli": 5_400_000},
                        "sleep_needed": {
                            "baseline_milli": 27_000_000,
                            "need_from_sleep_debt_milli": 600_000,
                        },
                    },
                }
            ],
            workout=[
                {
                    "id": "w1",
                    "created_at": "2026-09-01T18:00:00Z",
                    "sport_name": "running",
                    "score": {
                        "strain": 12.3,
                        "average_heart_rate": 150,
                        "zone_durations": {"zone_two_milli": 900_000},
                    },
                }
            ],
            cycle=[
                {
                    "id": 7,
                    "created_at": "2026-09-01T07:00:00Z",
                    "start": "2026-08-31T23:00:00Z",
                    "score": {"strain": 14.8, "kilojoule": 9000.0},
                }
            ],
            body={"height_meter": 1.8, "weight_kilogram": 75.0, "max_heart_rate": 190},
        )

        result = await sync_one_user(str(connected_user.id))

        assert result["cycles"] == 1
        async with async_session_factory() as db:
            [recovery] = await crud.list_recovery(db, str(connected_user.id))
            [sleep] = await crud.list_sleep(db, str(connected_user.id))
            [workout] = await crud.list_workout(db, str(connected_user.id))
            [cycle] = await crud.list_cycles(db, str(connected_user.id))
            body = await crud.get_body_measurement(db, str(connected_user.id))
        assert (recovery.score, recovery.hrv_rmssd_milli) == (72, 81.5)
        assert recovery.raw is not None and recovery.raw["score"]["spo2_percentage"] == 97.1
        assert (sleep.score, sleep.rem_sleep_milli, sleep.sleep_needed_milli) == (
            88,
            5_400_000,
            27_600_000,
        )
        assert (workout.sport_name, workout.zone_durations_milli) == (
            "running",
            [None, None, 900_000, None, None, None],
        )
        assert (cycle.score, cycle.kilojoule) == (14.8, 9000.0)
        assert body is not None and body.max_heart_rate == 190

    @respx.mock
    async def test_happy_path_a_later_sync_only_fetches_since_the_last_one(
        self, db_session, connected_user
    ):
        """Scope: the first sync fetches full history (no `start`); the
        next one starts from the last successful sync minus the overlap."""
        mock_whoop()
        recovery_route = respx.routes[0]

        await sync_one_user(str(connected_user.id))
        await sync_one_user(str(connected_user.id))

        assert "start" not in recovery_route.calls[0].request.url.params
        assert "start" in recovery_route.calls[1].request.url.params

    @respx.mock
    async def test_happy_path_refreshes_an_expired_token(self, db_session, expired_user):
        """Scope: an expired token must be refreshed, and the new tokens
        persisted, before the sync's fetch step ever runs."""
        refresh_route = respx.post(WHOOP_TOKEN_URL).mock(
            return_value=Response(
                200,
                json={
                    "access_token": "fresh-access-token",
                    "refresh_token": "fresh-refresh-token",
                    "expires_in": 3600,
                },
            )
        )
        mock_whoop()

        await sync_one_user(str(expired_user.id))

        # the refresh grant was actually exercised, not skipped
        assert refresh_route.called
        sent = refresh_route.calls.last.request.read()
        assert b"grant_type=refresh_token" in sent
        assert b"refresh_token=valid-refresh-token" in sent

        # the new tokens were persisted, encrypted, replacing the stale ones
        async with async_session_factory() as fresh_db:
            user = await crud.get_user(fresh_db, str(expired_user.id))
            assert decrypt_token(user.encrypted_access_token, settings.token_encryption_key) == (
                "fresh-access-token"
            )
            assert user.token_expires_at > utcnow()

    @respx.mock
    async def test_edge_case_rows_stored_before_full_detail_trigger_a_full_resync(
        self, db_session, connected_user
    ):
        """Scope: after the schema gained full-detail columns, a user whose rows
        have no `raw` yet gets their history re-fetched once, not just recent days."""
        mock_whoop(recovery=[{"cycle_id": 1, "created_at": "2026-09-01T07:00:00Z"}])
        recovery_route = respx.routes[0]
        await sync_one_user(str(connected_user.id))
        async with async_session_factory() as db:
            await db.execute(update(Recovery).values(raw=null()))  # SQL NULL, as pre-migration
            await db.commit()

        await sync_one_user(str(connected_user.id))

        assert "start" not in recovery_route.calls[1].request.url.params

    @respx.mock
    async def test_edge_case_raises_when_whoop_rejects_the_refresh_grant(
        self, db_session, expired_user
    ):
        """Scope: WHOOP can reject a refresh grant outright (e.g. the
        user revoked access on WHOOP's side) — must surface as
        UpstreamAuthError, the same domain-exception contract every
        other WHOOP failure follows, never a bare httpx.HTTPStatusError
        leaking out of this layer."""
        respx.post(WHOOP_TOKEN_URL).mock(
            return_value=Response(400, json={"error": "invalid_grant"})
        )

        with pytest.raises(UpstreamAuthError):
            await sync_one_user(str(expired_user.id))

    @respx.mock
    async def test_edge_case_a_revoked_grant_disconnects_the_user(self, db_session, expired_user):
        """Scope: a dead refresh token can't be retried into working, so the
        batch must stop scheduling this user until they reconnect."""
        respx.post(WHOOP_TOKEN_URL).mock(
            return_value=Response(400, json={"error": "invalid_grant"})
        )

        with pytest.raises(UpstreamAuthError):
            await sync_one_user(str(expired_user.id))

        async with async_session_factory() as db:
            user = await crud.get_user(db, str(expired_user.id))
            assert user.whoop_connected is False

    @respx.mock
    async def test_edge_case_a_transient_refresh_failure_keeps_the_user_connected(
        self, db_session, expired_user
    ):
        respx.post(WHOOP_TOKEN_URL).mock(return_value=Response(503))

        with pytest.raises(UpstreamAuthError):
            await sync_one_user(str(expired_user.id))

        async with async_session_factory() as db:
            user = await crud.get_user(db, str(expired_user.id))
            assert user.whoop_connected is True
