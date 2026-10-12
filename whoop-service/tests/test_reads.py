import uuid
from datetime import datetime

from httpx import ASGITransport, AsyncClient

from api.main import app
from services.whoop import crud
from services.whoop.models import User
from services.whoop.whoop_types import (
    RecoveryRecord,
    RecoveryScore,
    SleepRecord,
    SleepScore,
    WorkoutRecord,
    WorkoutScore,
)

_CREATED_AT = "2026-07-22T00:00:00Z"


def _client_as(token: str) -> AsyncClient:
    """An HTTP client authenticated with a specific bearer token — for
    read_token scoping tests, where the token under test isn't the
    operator API_KEY conftest's `client` fixture carries."""
    transport = ASGITransport(app=app)
    return AsyncClient(
        transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token}"}
    )


class TestCrossUserIsolation:
    """One query per record type, one adversarial test per type — recovery
    being scoped correctly isn't proof sleep/workout are, since each read
    route runs its own query."""

    async def test_edge_case_get_recovery_returns_only_that_users_rows(
        self, client, db_session, connected_user
    ):
        """Scope: a second user's row with the same whoop_record_id must
        never appear in connected_user's response."""
        other_user_id = uuid.uuid4()
        await crud.upsert_recovery(
            db_session,
            str(connected_user.id),
            RecoveryRecord(
                cycle_id=1, score=RecoveryScore(recovery_score=70), created_at=_CREATED_AT
            ),
        )
        other_user = User(id=other_user_id, whoop_connected=False)
        db_session.add(other_user)
        await db_session.commit()
        await crud.upsert_recovery(
            db_session,
            str(other_user_id),
            RecoveryRecord(
                cycle_id=1, score=RecoveryScore(recovery_score=99), created_at=_CREATED_AT
            ),
        )
        await db_session.commit()

        response = await client.get(f"/users/{connected_user.id}/recovery")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["score"] == 70
        assert body[0]["whoopRecordId"] == "1"

    async def test_edge_case_get_sleep_returns_only_that_users_rows(
        self, client, db_session, connected_user
    ):
        """Scope: same adversarial check as recovery's, for sleep."""
        other_user_id = uuid.uuid4()
        await crud.upsert_sleep(
            db_session,
            str(connected_user.id),
            SleepRecord(
                id="s1", score=SleepScore(sleep_performance_percentage=88), created_at=_CREATED_AT
            ),
        )
        other_user = User(id=other_user_id, whoop_connected=False)
        db_session.add(other_user)
        await db_session.commit()
        await crud.upsert_sleep(
            db_session,
            str(other_user_id),
            SleepRecord(
                id="s1", score=SleepScore(sleep_performance_percentage=12), created_at=_CREATED_AT
            ),
        )
        await db_session.commit()

        response = await client.get(f"/users/{connected_user.id}/sleep")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["score"] == 88

    async def test_edge_case_get_workout_returns_only_that_users_rows(
        self, client, db_session, connected_user
    ):
        """Scope: same adversarial check, for workout — with a
        fractional strain value, since that's the type this table
        actually stores."""
        other_user_id = uuid.uuid4()
        await crud.upsert_workout(
            db_session,
            str(connected_user.id),
            WorkoutRecord(id="w1", score=WorkoutScore(strain=4.559951), created_at=_CREATED_AT),
        )
        other_user = User(id=other_user_id, whoop_connected=False)
        db_session.add(other_user)
        await db_session.commit()
        await crud.upsert_workout(
            db_session,
            str(other_user_id),
            WorkoutRecord(id="w1", score=WorkoutScore(strain=16.887974), created_at=_CREATED_AT),
        )
        await db_session.commit()

        response = await client.get(f"/users/{connected_user.id}/workout")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["score"] == 4.559951


class TestReadAuthorization:
    """Two independent auth mechanisms guard these routes — the operator
    API_KEY and a per-user read_token — each tested for both the grant
    and the rejection it's responsible for."""

    async def test_happy_path_empty_for_a_user_with_no_records(self, client, connected_user):
        response = await client.get(f"/users/{connected_user.id}/recovery")

        assert response.status_code == 200
        assert response.json() == []

    async def test_edge_case_rejects_a_call_with_no_api_key(self, anonymous_client, connected_user):
        response = await anonymous_client.get(f"/users/{connected_user.id}/recovery")

        assert response.status_code == 401

    async def test_edge_case_rejects_the_real_read_token_with_no_bearer_prefix(
        self, connected_user
    ):
        """Scope: the real read_token, sent without the required `Bearer
        ` scheme, must still be rejected — str.removeprefix() only
        strips a prefix that's actually present, so a bare token would
        otherwise silently pass the comparison unchanged."""
        transport = ASGITransport(app=app)
        headers = {"Authorization": connected_user.read_token}  # no "Bearer " prefix
        async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
            response = await ac.get(f"/users/{connected_user.id}/recovery")

        assert response.status_code == 401

    async def test_happy_path_a_users_own_read_token_grants_access_to_their_own_data(
        self, connected_user
    ):
        async with _client_as(connected_user.read_token) as ac:
            response = await ac.get(f"/users/{connected_user.id}/recovery")

        assert response.status_code == 200

    async def test_edge_case_a_users_read_token_does_not_grant_access_to_another_users_data(
        self, db_session, connected_user
    ):
        """Scope: the gap a shared master key alone would leave open —
        holding a valid key must not mean holding access to *every*
        user's data."""
        other_user = User(id=uuid.uuid4(), whoop_connected=True, read_token="other-users-token")
        db_session.add(other_user)
        await db_session.commit()

        async with _client_as(connected_user.read_token) as ac:
            response = await ac.get(f"/users/{other_user.id}/recovery")

        assert response.status_code == 401

    async def test_happy_path_the_master_api_key_still_grants_access_to_any_user(
        self, client, connected_user
    ):
        """Scope: the operator-level key is unaffected by per-user
        scoping."""
        response = await client.get(f"/users/{connected_user.id}/recovery")

        assert response.status_code == 200

    async def test_happy_path_sleep_and_workout_are_scoped_the_same_way(
        self, client, db_session, connected_user
    ):
        await crud.upsert_sleep(
            db_session,
            str(connected_user.id),
            SleepRecord(
                id="s1", score=SleepScore(sleep_performance_percentage=88), created_at=_CREATED_AT
            ),
        )
        await crud.upsert_workout(
            db_session,
            str(connected_user.id),
            WorkoutRecord(id="w1", score=WorkoutScore(strain=12), created_at=_CREATED_AT),
        )
        await db_session.commit()

        sleep_response = await client.get(f"/users/{connected_user.id}/sleep")
        workout_response = await client.get(f"/users/{connected_user.id}/workout")

        assert sleep_response.json()[0]["score"] == 88
        assert workout_response.json()[0]["score"] == 12
        assert isinstance(datetime.fromisoformat(sleep_response.json()[0]["recordedAt"]), datetime)


class TestETag:
    """content_hash-derived ETags — stable across a no-op resync, changed
    when the underlying record actually changes."""

    async def test_happy_path_round_trips_to_304(self, client, db_session, connected_user):
        await crud.upsert_recovery(
            db_session,
            str(connected_user.id),
            RecoveryRecord(
                cycle_id=1, score=RecoveryScore(recovery_score=70), created_at=_CREATED_AT
            ),
        )
        await db_session.commit()

        first = await client.get(f"/users/{connected_user.id}/recovery")
        etag = first.headers["etag"]

        second = await client.get(
            f"/users/{connected_user.id}/recovery", headers={"If-None-Match": etag}
        )

        assert first.status_code == 200
        assert second.status_code == 304
        assert second.content == b""

    async def test_happy_path_changes_when_the_record_actually_changes(
        self, client, db_session, connected_user
    ):
        await crud.upsert_recovery(
            db_session,
            str(connected_user.id),
            RecoveryRecord(
                cycle_id=1, score=RecoveryScore(recovery_score=70), created_at=_CREATED_AT
            ),
        )
        await db_session.commit()
        before = await client.get(f"/users/{connected_user.id}/recovery")

        # Re-sync the same cycle with a different score — content_hash changes,
        # so the ETag must change too, even though whoop_record_id is unchanged.
        await crud.upsert_recovery(
            db_session,
            str(connected_user.id),
            RecoveryRecord(
                cycle_id=1, score=RecoveryScore(recovery_score=71), created_at=_CREATED_AT
            ),
        )
        await db_session.commit()
        after = await client.get(
            f"/users/{connected_user.id}/recovery",
            headers={"If-None-Match": before.headers["etag"]},
        )

        assert after.status_code == 200
        assert after.headers["etag"] != before.headers["etag"]
        assert after.json()[0]["score"] == 71

    async def test_edge_case_stable_across_a_no_op_resync(self, client, db_session, connected_user):
        """Scope: a re-sync that sends the exact same record twice is the
        common case (a batch that re-fetches everyone's data on every
        run) — content_hash is what makes crud.py's upsert a genuine
        no-op there, and this ETag staying identical is the
        caller-visible proof that it did."""
        record = RecoveryRecord(
            cycle_id=1, score=RecoveryScore(recovery_score=70), created_at=_CREATED_AT
        )
        await crud.upsert_recovery(db_session, str(connected_user.id), record)
        await db_session.commit()
        before = await client.get(f"/users/{connected_user.id}/recovery")

        await crud.upsert_recovery(db_session, str(connected_user.id), record.model_copy())
        await db_session.commit()
        after = await client.get(f"/users/{connected_user.id}/recovery")

        assert after.headers["etag"] == before.headers["etag"]

    async def test_edge_case_stable_across_a_no_op_resync_with_fractional_strain(
        self, client, db_session, connected_user
    ):
        """Scope: regression test — WHOOP's strain is a 0-21 decimal
        (e.g. 4.559951), not an integer. A resync with the exact same
        fractional value must still be a genuine no-op, the same
        guarantee the recovery test above proves for an integer score."""
        record = WorkoutRecord(id="w1", score=WorkoutScore(strain=4.559951), created_at=_CREATED_AT)
        await crud.upsert_workout(db_session, str(connected_user.id), record)
        await db_session.commit()
        before = await client.get(f"/users/{connected_user.id}/workout")

        await crud.upsert_workout(db_session, str(connected_user.id), record.model_copy())
        await db_session.commit()
        after = await client.get(f"/users/{connected_user.id}/workout")

        assert after.headers["etag"] == before.headers["etag"]
        assert after.json()[0]["score"] == 4.559951

    async def test_edge_case_changes_when_only_the_fractional_part_of_strain_changes(
        self, client, db_session, connected_user
    ):
        """Scope: a strain change as small as a fractional-only
        difference (16.887974 -> 16.887975) must still register as a
        real change, not be swallowed by any rounding along the write
        path."""
        await crud.upsert_workout(
            db_session,
            str(connected_user.id),
            WorkoutRecord(id="w1", score=WorkoutScore(strain=16.887974), created_at=_CREATED_AT),
        )
        await db_session.commit()
        before = await client.get(f"/users/{connected_user.id}/workout")

        await crud.upsert_workout(
            db_session,
            str(connected_user.id),
            WorkoutRecord(id="w1", score=WorkoutScore(strain=16.887975), created_at=_CREATED_AT),
        )
        await db_session.commit()
        after = await client.get(
            f"/users/{connected_user.id}/workout",
            headers={"If-None-Match": before.headers["etag"]},
        )

        assert after.status_code == 200
        assert after.headers["etag"] != before.headers["etag"]
        assert after.json()[0]["score"] == 16.887975


class TestFullDetail:
    async def test_happy_path_cycles_are_returned_newest_first_with_their_metrics(
        self, client, db_session, connected_user
    ):
        from services.whoop.whoop_types import CycleRecord, CycleScore

        for i, strain in ((1, 8.0), (2, 15.5)):
            await crud.upsert_cycle(
                db_session,
                str(connected_user.id),
                CycleRecord(
                    id=i,
                    created_at=f"2026-09-0{i}T07:00:00Z",
                    start=f"2026-09-0{i}T00:00:00Z",
                    score=CycleScore(strain=strain, kilojoule=8000.0),
                ),
            )
        await db_session.commit()

        response = await client.get(f"/users/{connected_user.id}/cycles")

        assert response.status_code == 200
        body = response.json()
        assert [c["score"] for c in body] == [15.5, 8.0]
        assert body[0]["kilojoule"] == 8000.0

    async def test_happy_path_profile_returns_name_and_body_measurement(
        self, client, db_session, connected_user
    ):
        from services.whoop.whoop_types import BodyMeasurement

        connected_user.first_name = "Sam"
        await crud.upsert_body_measurement(
            db_session,
            str(connected_user.id),
            BodyMeasurement(height_meter=1.8, weight_kilogram=75.0, max_heart_rate=190),
        )
        await db_session.commit()

        response = await client.get(f"/users/{connected_user.id}/profile")

        assert response.status_code == 200
        assert response.json() == {
            "firstName": "Sam",
            "lastName": None,
            "heightMeter": 1.8,
            "weightKilogram": 75.0,
            "maxHeartRate": 190,
        }
