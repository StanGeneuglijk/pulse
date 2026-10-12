import uuid
from datetime import timedelta

from core.clock import utcnow
from services.insight.config import INSIGHT_SPEND_LIMIT_USD
from services.insight.crud import write_insight_job_log
from services.insight.lock import acquire_insight_lock, release_insight_lock
from tests.conftest import seed_recovery


async def test_generate_returns_201_with_camel_case_body(client, db_session, whoop_tables):
    user_id = uuid.uuid4()
    await seed_recovery(db_session, user_id, 85, utcnow() - timedelta(days=1))

    response = await client.post(f"/insights/generate/{user_id}")

    assert response.status_code == 201
    body = response.json()
    assert body["userId"] == str(user_id)
    assert "periodStart" in body and "periodEnd" in body
    assert "content" in body


async def test_generate_with_no_data_returns_422(client, db_session, whoop_tables):
    user_id = uuid.uuid4()

    response = await client.post(f"/insights/generate/{user_id}")

    assert response.status_code == 422


async def test_generate_rejects_when_already_locked(client, db_session, whoop_tables):
    user_id = uuid.uuid4()
    await seed_recovery(db_session, user_id, 85, utcnow() - timedelta(days=1))
    assert await acquire_insight_lock(user_id, ttl_seconds=30) is True
    try:
        response = await client.post(f"/insights/generate/{user_id}")
        assert response.status_code == 409
    finally:
        await release_insight_lock(user_id)


async def test_list_and_latest_after_generation(client, db_session, whoop_tables):
    user_id = uuid.uuid4()
    await seed_recovery(db_session, user_id, 85, utcnow() - timedelta(days=1))
    generated = await client.post(f"/insights/generate/{user_id}")
    assert generated.status_code == 201

    listed = await client.get(f"/insights/{user_id}")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    latest = await client.get(f"/insights/{user_id}/latest")
    assert latest.status_code == 200
    assert latest.json()["id"] == generated.json()["id"]


async def test_latest_with_no_insight_returns_404(client, db_session):
    user_id = uuid.uuid4()

    response = await client.get(f"/insights/{user_id}/latest")

    assert response.status_code == 404


async def test_unauthenticated_request_is_rejected(anonymous_client, db_session):
    response = await anonymous_client.get(f"/insights/{uuid.uuid4()}")
    assert response.status_code == 401


async def test_spend_endpoint_reports_zero_before_any_generation(client, db_session):
    response = await client.get("/insights/spend")

    assert response.status_code == 200
    body = response.json()
    assert body["spentUsd"] == 0
    assert body["limitUsd"] == INSIGHT_SPEND_LIMIT_USD


async def test_generate_returns_402_once_spend_cap_is_reached(client, db_session, whoop_tables):
    user_id = uuid.uuid4()
    await seed_recovery(db_session, user_id, 85, utcnow() - timedelta(days=1))
    over_cap_tokens = int(INSIGHT_SPEND_LIMIT_USD / (10.00 / 1_000_000)) + 1_000
    await write_insight_job_log(
        db_session,
        user_id=uuid.uuid4(),
        status="success",
        period_type="weekly",
        duration_ms=1.0,
        model_name="claude-sonnet-5",
        input_tokens=0,
        output_tokens=over_cap_tokens,
    )

    response = await client.post(f"/insights/generate/{user_id}")

    assert response.status_code == 402


async def test_generate_accepts_a_period_query_param(client, db_session, whoop_tables):
    user_id = uuid.uuid4()
    await seed_recovery(db_session, user_id, 85, utcnow())

    response = await client.post(f"/insights/generate/{user_id}?period=daily")

    assert response.status_code == 201
    assert response.json()["periodType"] == "daily"


async def test_generate_rejects_an_unknown_period(client, db_session, whoop_tables):
    user_id = uuid.uuid4()

    response = await client.post(f"/insights/generate/{user_id}?period=yearly")

    assert response.status_code == 422


async def test_daily_and_weekly_latest_are_independent(client, db_session, whoop_tables):
    user_id = uuid.uuid4()
    await seed_recovery(db_session, user_id, 85, utcnow())

    daily = await client.post(f"/insights/generate/{user_id}?period=daily")
    assert daily.status_code == 201
    weekly = await client.post(f"/insights/generate/{user_id}?period=weekly")
    assert weekly.status_code == 201
    assert daily.json()["id"] != weekly.json()["id"]

    latest_daily = await client.get(f"/insights/{user_id}/latest?period=daily")
    assert latest_daily.json()["id"] == daily.json()["id"]
    latest_weekly = await client.get(f"/insights/{user_id}/latest?period=weekly")
    assert latest_weekly.json()["id"] == weekly.json()["id"]


async def test_activity_is_recorded_for_generate_and_list(client, db_session, whoop_tables):
    user_id = uuid.uuid4()
    await seed_recovery(db_session, user_id, 85, utcnow() - timedelta(days=1))
    await client.post(f"/insights/generate/{user_id}")
    await client.get(f"/insights/{user_id}")

    response = await client.get(f"/insights/{user_id}/activity")

    assert response.status_code == 200
    routes = [row["route"] for row in response.json()]
    assert "generate:weekly" in routes
    assert "list" in routes


async def test_usage_summary_counts_generated_insights(client, db_session, whoop_tables):
    user_id = uuid.uuid4()
    await seed_recovery(db_session, user_id, 85, utcnow() - timedelta(hours=1))
    await client.post(f"/insights/generate/{user_id}?period=daily")

    response = await client.get(f"/insights/{user_id}/usage")

    assert response.status_code == 200
    body = response.json()
    assert body["totalGenerated"] == 1
    assert body["generatedByPeriod"] == {"daily": 1}
    assert body["lastGeneratedAt"] is not None
