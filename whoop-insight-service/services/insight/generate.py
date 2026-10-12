"""Orchestration for one insight: caps -> lock -> read data -> prompt -> LLM ->
upsert -> job log. The only module that wires those pieces together.
"""

import time
import uuid
from datetime import timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.clock import utcnow
from core.logging import get_logger
from services.insight.config import (
    INSIGHT_LOCK_TTL_SECONDS,
    INSIGHT_PER_USER_SPEND_LIMIT_USD,
    INSIGHT_SPEND_LIMIT_USD,
    PERIOD_POLICY,
    PROMPT_VERSION,
    InsightPeriod,
)
from services.insight.crud import (
    content_hash,
    total_spend_usd,
    upsert_insight,
    write_insight_job_log,
)
from services.insight.exceptions import (
    GenerationLockedError,
    InsufficientDataError,
    SpendLimitExceededError,
)
from services.insight.llm import LLMClient
from services.insight.lock import acquire_insight_lock, release_insight_lock
from services.insight.models import Insight
from services.insight.nutrition_read import fetch_active_goal
from services.insight.nutrition_read import fetch_window as fetch_nutrition_window
from services.insight.prompt import build_prompt
from services.insight.whoop_read import fetch_window

logger = get_logger(__name__)


async def generate_insight(
    db: AsyncSession, llm_client: LLMClient, user_id: uuid.UUID, period: InsightPeriod = "weekly"
) -> Insight:
    """Generate (or return the unchanged) insight for `user_id`'s trailing
    `period` window; PERIOD_POLICY sets the window, effort and output ceiling.

    Raises:
        SpendLimitExceededError: Per-user or platform cap reached (checked first).
        GenerationLockedError: A generation is already running for this user.
        InsufficientDataError: No WHOOP data in the window — raised before billing.
        LLMProviderError: The provider call failed.
    """
    policy = PERIOD_POLICY[period]

    # Per-user cap first: the one a user's own overuse trips.
    user_spent = await total_spend_usd(db, user_id=user_id)
    if user_spent >= INSIGHT_PER_USER_SPEND_LIMIT_USD:
        raise SpendLimitExceededError(user_spent, INSIGHT_PER_USER_SPEND_LIMIT_USD)

    spent = await total_spend_usd(db)
    if spent >= INSIGHT_SPEND_LIMIT_USD:
        raise SpendLimitExceededError(spent, INSIGHT_SPEND_LIMIT_USD)

    if not await acquire_insight_lock(user_id, ttl_seconds=INSIGHT_LOCK_TTL_SECONDS):
        raise GenerationLockedError(str(user_id))

    structlog.contextvars.bind_contextvars(user_id=str(user_id), period=period)
    started_at = time.monotonic()
    try:
        logger.info("insight_generation_started")
        until = utcnow()
        since = until - timedelta(days=policy.window_days)
        window = await fetch_window(db, user_id, since=since, until=until)
        if window.is_empty():
            raise InsufficientDataError(str(user_id), policy.window_days)

        # Optional source: no meals/goal just means a WHOOP-only prompt.
        nutrition_window = await fetch_nutrition_window(db, user_id, since=since, until=until)
        active_goal = await fetch_active_goal(db, user_id)

        # End the read transaction before the slow LLM call, so a pooled
        # database connection isn't held idle for its whole duration.
        await db.commit()

        system, user_prompt = build_prompt(
            window, period, nutrition_window=nutrition_window, active_goal=active_goal
        )
        result = await llm_client.generate(
            system=system,
            user_prompt=user_prompt,
            max_tokens=policy.max_output_tokens,
            effort=policy.effort,
        )

        insight = await upsert_insight(
            db,
            user_id=user_id,
            period_type=period,
            period_start=since,
            period_end=until,
            prompt_version=PROMPT_VERSION,
            model_name=result.model,
            content=result.text,
            content_hash_value=content_hash(
                window, PROMPT_VERSION, nutrition_window=nutrition_window, active_goal=active_goal
            ),
        )
        logger.info("insight_generation_complete", insight_id=str(insight.id))
        await write_insight_job_log(
            db,
            user_id=user_id,
            status="success",
            duration_ms=(time.monotonic() - started_at) * 1000,
            period_type=period,
            model_name=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
        return insight
    except Exception as exc:
        logger.exception("insight_generation_failed")
        # A failed flush leaves the session unusable until rolled back,
        # which would also lose the job-log row below.
        await db.rollback()
        await write_insight_job_log(
            db,
            user_id=user_id,
            status="failed",
            duration_ms=(time.monotonic() - started_at) * 1000,
            period_type=period,
            error_message=str(exc),
        )
        raise
    finally:
        await release_insight_lock(user_id)
        structlog.contextvars.clear_contextvars()
