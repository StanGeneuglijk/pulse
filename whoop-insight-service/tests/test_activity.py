import uuid
from datetime import timedelta

from core.clock import utcnow
from services.insight.activity_log import log_activity
from services.insight.crud import list_activity, usage_summary
from services.insight.generate import generate_insight
from tests.conftest import FakeLLMClient, seed_recovery


async def test_log_activity_writes_a_row(db_session):
    user_id = uuid.uuid4()

    await log_activity(db_session, user_id, "list")

    rows = await list_activity(db_session, user_id)
    assert [r.route for r in rows] == ["list"]


async def test_usage_summary_reflects_generated_insights_by_period(db_session, whoop_tables):
    user_id = uuid.uuid4()
    await seed_recovery(db_session, user_id, 85, utcnow() - timedelta(hours=1))
    fake = FakeLLMClient()

    await generate_insight(db_session, fake, user_id, "daily")
    await generate_insight(db_session, fake, user_id, "weekly")
    await log_activity(db_session, user_id, "list")

    summary = await usage_summary(db_session, user_id)

    assert summary["total_generated"] == 2
    assert summary["generated_by_period"] == {"daily": 1, "weekly": 1}
    assert summary["activity_count"] == 1
    assert summary["last_generated_at"] is not None
