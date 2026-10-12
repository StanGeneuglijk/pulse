import uuid

import pytest

from services.nutrition.config import NUTRITION_PER_USER_SPEND_LIMIT_USD, NUTRITION_SPEND_LIMIT_USD
from services.nutrition.crud import enforce_spend_cap, total_spend_usd, write_nutrition_job_log
from services.nutrition.exceptions import SpendLimitExceededError
from services.nutrition.pricing import estimate_cost_usd, estimate_transcription_cost_usd


def test_estimate_cost_uses_the_configured_models_rate():
    cost = estimate_cost_usd("claude-sonnet-5", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == pytest.approx(2.00 + 10.00)


def test_estimate_transcription_cost_uses_the_configured_models_rate():
    cost = estimate_transcription_cost_usd("whisper-1", duration_seconds=120.0)
    assert cost == pytest.approx(0.006 * 2)


async def test_total_spend_sums_only_successful_rows(db_session):
    user_id = uuid.uuid4()
    await write_nutrition_job_log(
        db_session,
        user_id=user_id,
        status="success",
        model_name="claude-sonnet-5",
        input_tokens=1_000_000,
        output_tokens=0,
        duration_ms=1.0,
    )
    await write_nutrition_job_log(
        db_session, user_id=user_id, status="failed", error_message="boom", duration_ms=1.0
    )

    assert await total_spend_usd(db_session) == pytest.approx(2.00)


async def test_total_spend_folds_in_transcription_cost(db_session):
    user_id = uuid.uuid4()
    await write_nutrition_job_log(
        db_session,
        user_id=user_id,
        status="success",
        model_name="claude-sonnet-5",
        input_tokens=1_000_000,
        output_tokens=0,
        duration_ms=1.0,
    )
    await write_nutrition_job_log(
        db_session,
        user_id=user_id,
        status="success",
        model_name="whisper-1",
        audio_seconds=60.0,
        duration_ms=1.0,
    )

    assert await total_spend_usd(db_session) == pytest.approx(2.00 + 0.006)


async def test_enforce_spend_cap_raises_once_the_platform_cap_is_reached(db_session):
    user_id = uuid.uuid4()
    over_cap_seconds = (NUTRITION_SPEND_LIMIT_USD / 0.006) * 60 + 60
    await write_nutrition_job_log(
        db_session,
        user_id=user_id,
        status="success",
        model_name="whisper-1",
        audio_seconds=over_cap_seconds,
        duration_ms=1.0,
    )

    with pytest.raises(SpendLimitExceededError):
        await enforce_spend_cap(db_session, user_id)


async def test_enforce_spend_cap_passes_under_the_cap(db_session):
    await enforce_spend_cap(db_session, uuid.uuid4())


async def test_enforce_spend_cap_raises_once_that_users_own_cap_is_reached(db_session):
    """A different, smaller cap than the platform-wide one — one user's
    own overuse must stop that user without needing to also exhaust the
    shared platform budget."""
    user_id = uuid.uuid4()
    over_per_user_cap_seconds = (NUTRITION_PER_USER_SPEND_LIMIT_USD / 0.006) * 60 + 60
    await write_nutrition_job_log(
        db_session,
        user_id=user_id,
        status="success",
        model_name="whisper-1",
        audio_seconds=over_per_user_cap_seconds,
        duration_ms=1.0,
    )

    with pytest.raises(SpendLimitExceededError):
        await enforce_spend_cap(db_session, user_id)

    assert await total_spend_usd(db_session) < NUTRITION_SPEND_LIMIT_USD


async def test_another_users_spend_never_counts_against_this_users_cap(db_session):
    user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    over_per_user_cap_seconds = (NUTRITION_PER_USER_SPEND_LIMIT_USD / 0.006) * 60 + 60
    await write_nutrition_job_log(
        db_session,
        user_id=other_user_id,
        status="success",
        model_name="whisper-1",
        audio_seconds=over_per_user_cap_seconds,
        duration_ms=1.0,
    )

    await enforce_spend_cap(db_session, user_id)  # must not raise
