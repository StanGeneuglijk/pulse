import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from core.clock import utcnow
from services.insight.config import PERIOD_POLICY
from services.insight.exceptions import InsufficientDataError, LLMProviderError
from services.insight.generate import generate_insight
from services.insight.llm import LLMResult
from services.insight.models import Insight, InsightJobLog
from tests.conftest import FakeLLMClient, seed_goal, seed_nutrition_log, seed_recovery


@pytest.mark.parametrize("period", ["daily", "weekly", "monthly"])
async def test_generate_insight_applies_the_periods_policy(db_session, whoop_tables, period):
    user_id = uuid.uuid4()
    policy = PERIOD_POLICY[period]
    # Seed one row just inside the window and one just outside it, so a
    # wrong window_days for this period would visibly change the count
    # fetch_window sees (covered directly in test_whoop_read.py) — here
    # the actual behavior under test is that the LLM call itself receives
    # this period's effort/max_tokens, not another period's.
    await seed_recovery(
        db_session, user_id, 85, utcnow() - timedelta(days=max(policy.window_days - 1, 0))
    )
    fake = FakeLLMClient()

    insight = await generate_insight(db_session, fake, user_id, period)

    assert insight.period_type == period
    assert fake.last_effort == policy.effort
    assert fake.last_max_tokens == policy.max_output_tokens


async def test_generate_insight_persists_a_row(db_session, whoop_tables):
    user_id = uuid.uuid4()
    await seed_recovery(db_session, user_id, 85, utcnow() - timedelta(days=1))
    fake = FakeLLMClient(text="Solid recovery week.")

    insight = await generate_insight(db_session, fake, user_id)

    assert insight.content == "Solid recovery week."
    assert fake.calls == 1

    log_rows = (
        await db_session.execute(
            select(InsightJobLog).where(InsightJobLog.user_id == user_id)
        )
    ).scalars().all()
    assert len(log_rows) == 1
    assert log_rows[0].status == "success"


async def test_empty_window_raises_before_any_llm_call(db_session, whoop_tables):
    user_id = uuid.uuid4()
    fake = FakeLLMClient()

    with pytest.raises(InsufficientDataError):
        await generate_insight(db_session, fake, user_id)

    assert fake.calls == 0

    log_rows = (
        await db_session.execute(
            select(InsightJobLog).where(InsightJobLog.user_id == user_id)
        )
    ).scalars().all()
    assert len(log_rows) == 1
    assert log_rows[0].status == "failed"


async def test_llm_provider_failure_logs_and_does_not_persist_an_insight(db_session, whoop_tables):
    user_id = uuid.uuid4()
    await seed_recovery(db_session, user_id, 85, utcnow() - timedelta(days=1))

    class FailingLLMClient:
        async def generate(
            self, *, system: str, user_prompt: str, max_tokens: int, effort: str
        ) -> LLMResult:
            raise LLMProviderError("upstream 529")

    with pytest.raises(LLMProviderError):
        await generate_insight(db_session, FailingLLMClient(), user_id)

    insights = (
        await db_session.execute(select(Insight).where(Insight.user_id == user_id))
    ).scalars().all()
    assert insights == []

    log_rows = (
        await db_session.execute(
            select(InsightJobLog).where(InsightJobLog.user_id == user_id)
        )
    ).scalars().all()
    assert log_rows[0].status == "failed"
    assert "529" in log_rows[0].error_message


async def test_generate_insight_folds_nutrition_and_goal_into_the_real_prompt(
    db_session, whoop_tables
):
    """task 11's end-to-end acceptance: the actual prompt generate_insight
    builds — not just build_prompt() in isolation — contains nutrition
    figures and goal context when whoop-nutrition-service has data for
    this user, through the real fetch_nutrition_window/fetch_active_goal
    calls wired into generate.py."""
    user_id = uuid.uuid4()
    await seed_recovery(db_session, user_id, 85, utcnow() - timedelta(days=1))
    await seed_nutrition_log(
        db_session,
        user_id,
        calories=450,
        protein_g=49.0,
        carbs_g=44.0,
        fat_g=6.5,
        logged_at=utcnow() - timedelta(days=1),
    )
    await seed_goal(db_session, user_id, goal_type="weight_loss", target_calories=1800)
    fake = FakeLLMClient()

    await generate_insight(db_session, fake, user_id, "weekly")

    assert "450 kcal" in fake.last_user_prompt
    assert "weight_loss" in fake.last_user_prompt


async def test_generate_insight_prompt_is_unchanged_with_no_nutrition_data(
    db_session, whoop_tables
):
    """The other half of the same acceptance: a user with no nutrition
    history at all gets exactly the pre-integration prompt shape."""
    user_id = uuid.uuid4()
    await seed_recovery(db_session, user_id, 85, utcnow() - timedelta(days=1))
    fake = FakeLLMClient()

    await generate_insight(db_session, fake, user_id, "weekly")

    assert "Meals logged" not in fake.last_user_prompt
    assert "goal" not in fake.last_user_prompt.lower()
