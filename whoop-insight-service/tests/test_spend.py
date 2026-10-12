import uuid
from datetime import timedelta

import pytest

from core.clock import utcnow
from services.insight.config import INSIGHT_PER_USER_SPEND_LIMIT_USD, INSIGHT_SPEND_LIMIT_USD
from services.insight.crud import total_spend_usd, write_insight_job_log
from services.insight.exceptions import SpendLimitExceededError
from services.insight.generate import generate_insight
from services.insight.pricing import estimate_cost_usd
from tests.conftest import FakeLLMClient, seed_recovery


def test_estimate_cost_uses_the_configured_models_rate():
    cost = estimate_cost_usd("claude-sonnet-5", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == pytest.approx(2.00 + 10.00)


def test_estimate_cost_falls_back_to_the_most_expensive_row_for_an_unknown_model():
    known = estimate_cost_usd("claude-sonnet-5", input_tokens=1000, output_tokens=1000)
    unknown = estimate_cost_usd("some-future-model", input_tokens=1000, output_tokens=1000)
    assert unknown >= known


async def test_total_spend_sums_only_successful_rows(db_session):
    user_id = uuid.uuid4()
    await write_insight_job_log(
        db_session,
        user_id=user_id,
        status="success",
        period_type="weekly",
        duration_ms=1.0,
        model_name="claude-sonnet-5",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    await write_insight_job_log(
        db_session,
        user_id=user_id,
        status="failed",
        period_type="weekly",
        duration_ms=1.0,
        error_message="boom",
    )

    assert await total_spend_usd(db_session) == pytest.approx(2.00)


async def test_generate_insight_refuses_once_the_cap_is_reached(db_session, whoop_tables):
    user_id = uuid.uuid4()
    await seed_recovery(db_session, user_id, 85, utcnow() - timedelta(days=1))

    # One oversized logged call is enough to push cumulative spend past
    # the configured cap without needing INSIGHT_SPEND_LIMIT_USD real
    # generations.
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

    fake = FakeLLMClient()
    with pytest.raises(SpendLimitExceededError):
        await generate_insight(db_session, fake, user_id)

    assert fake.calls == 0  # the cap is checked before any LLM call


async def test_generate_insight_refuses_once_that_users_own_cap_is_reached(
    db_session, whoop_tables
):
    """A different, smaller cap than the platform-wide one — one user's
    own overuse must stop that user, without needing to also exhaust the
    shared platform budget every other user draws from."""
    user_id = uuid.uuid4()
    await seed_recovery(db_session, user_id, 85, utcnow() - timedelta(days=1))

    over_cap_tokens = int(INSIGHT_PER_USER_SPEND_LIMIT_USD / (10.00 / 1_000_000)) + 1_000
    await write_insight_job_log(
        db_session,
        user_id=user_id,
        status="success",
        period_type="weekly",
        duration_ms=1.0,
        model_name="claude-sonnet-5",
        input_tokens=0,
        output_tokens=over_cap_tokens,
    )

    fake = FakeLLMClient()
    with pytest.raises(SpendLimitExceededError):
        await generate_insight(db_session, fake, user_id)

    assert fake.calls == 0
    # Nowhere near the platform-wide cap — this user's own cap is what
    # tripped, not a coincidental platform-wide exhaustion.
    assert await total_spend_usd(db_session) < INSIGHT_SPEND_LIMIT_USD


async def test_another_users_spend_never_counts_against_this_users_cap(db_session, whoop_tables):
    user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    await seed_recovery(db_session, user_id, 85, utcnow() - timedelta(days=1))

    over_cap_tokens = int(INSIGHT_PER_USER_SPEND_LIMIT_USD / (10.00 / 1_000_000)) + 1_000
    await write_insight_job_log(
        db_session,
        user_id=other_user_id,
        status="success",
        period_type="weekly",
        duration_ms=1.0,
        model_name="claude-sonnet-5",
        input_tokens=0,
        output_tokens=over_cap_tokens,
    )

    fake = FakeLLMClient()
    insight = await generate_insight(db_session, fake, user_id)

    assert insight is not None
    assert fake.calls == 1
