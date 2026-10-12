"""Persistence for insights: the idempotent upsert, reads, job/activity logs
and the spend aggregate.
"""

import hashlib
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from services.insight.config import InsightPeriod
from services.insight.models import Insight, InsightActivityLog, InsightJobLog
from services.insight.nutrition_read import ActiveGoal, NutritionWindow
from services.insight.pricing import estimate_cost_usd
from services.insight.whoop_read import WhoopWindow

_LIST_PAGE_SIZE = 50


def content_hash(
    window: WhoopWindow,
    prompt_version: str,
    *,
    nutrition_window: NutritionWindow | None = None,
    active_goal: ActiveGoal | None = None,
) -> str:
    """Fingerprint of every input a generation used (WHOOP data, meals, goal,
    prompt version). Unchanged inputs -> unchanged hash -> the upsert skips the write.
    """
    parts = [prompt_version]
    for record in sorted(window.recovery, key=lambda r: r.recorded_at):
        parts.append(f"r:{record.score}:{record.recorded_at.isoformat()}")
    for record in sorted(window.sleep, key=lambda r: r.recorded_at):
        parts.append(f"s:{record.score}:{record.recorded_at.isoformat()}")
    for record in sorted(window.workout, key=lambda r: r.recorded_at):
        parts.append(f"w:{record.score}:{record.recorded_at.isoformat()}")
    if nutrition_window is not None:
        for meal in sorted(nutrition_window.meals, key=lambda m: m.logged_at):
            parts.append(f"n:{meal.calories}:{meal.logged_at.isoformat()}")
    if active_goal is not None:
        parts.append(
            f"g:{active_goal.goal_type}:{active_goal.target_calories}:"
            f"{active_goal.target_protein_g}:{active_goal.target_carbs_g}:"
            f"{active_goal.target_fat_g}"
        )
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


async def upsert_insight(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    period_type: InsightPeriod,
    period_start: datetime,
    period_end: datetime,
    prompt_version: str,
    model_name: str,
    content: str,
    content_hash_value: str,
) -> Insight:
    """Upsert one insight keyed on (user, period type, start, end, prompt version);
    skipped when the content hash is unchanged.
    """
    stmt = insert(Insight).values(
        user_id=user_id,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
        prompt_version=prompt_version,
        model_name=model_name,
        content=content,
        content_hash=content_hash_value,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_user_insight_period",
        set_={
            "model_name": stmt.excluded.model_name,
            "content": stmt.excluded.content,
            "content_hash": stmt.excluded.content_hash,
        },
        where=Insight.content_hash != stmt.excluded.content_hash,
    )
    await db.execute(stmt)
    await db.commit()

    # Re-select rather than RETURNING (which is empty when `where=` skips the
    # update). populate_existing: the Core UPDATE bypassed the identity map,
    # so a cached object from an earlier call would otherwise be stale.
    existing = await db.execute(
        select(Insight)
        .where(
            Insight.user_id == user_id,
            Insight.period_type == period_type,
            Insight.period_start == period_start,
            Insight.period_end == period_end,
            Insight.prompt_version == prompt_version,
        )
        .execution_options(populate_existing=True)
    )
    return existing.scalar_one()


async def list_insights(
    db: AsyncSession, user_id: uuid.UUID, *, period_type: InsightPeriod | None = None
) -> list[Insight]:
    """A user's insights, newest first, optionally for one period type."""
    stmt = select(Insight).where(Insight.user_id == user_id)
    if period_type is not None:
        stmt = stmt.where(Insight.period_type == period_type)
    result = await db.execute(stmt.order_by(Insight.created_at.desc()).limit(_LIST_PAGE_SIZE))
    return list(result.scalars().all())


async def get_latest_insight(
    db: AsyncSession, user_id: uuid.UUID, *, period_type: InsightPeriod
) -> Insight | None:
    result = await db.execute(
        select(Insight)
        .where(Insight.user_id == user_id, Insight.period_type == period_type)
        .order_by(Insight.created_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def write_insight_job_log(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    status: str,
    period_type: InsightPeriod,
    duration_ms: float,
    model_name: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    error_message: str | None = None,
) -> None:
    """Record one generation attempt; commits on its own."""
    db.add(
        InsightJobLog(
            user_id=user_id,
            status=status,
            period_type=period_type,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=duration_ms,
            error_message=error_message,
        )
    )
    await db.commit()


async def total_spend_usd(db: AsyncSession, *, user_id: uuid.UUID | None = None) -> float:
    """Estimated cumulative spend over every successful generation, across
    all users or for one. Token counts are summed per model in SQL, so the
    cost stays one small query however long the log grows."""
    stmt = (
        select(
            InsightJobLog.model_name,
            func.coalesce(func.sum(InsightJobLog.input_tokens), 0),
            func.coalesce(func.sum(InsightJobLog.output_tokens), 0),
        )
        .where(InsightJobLog.status == "success", InsightJobLog.model_name.is_not(None))
        .group_by(InsightJobLog.model_name)
    )
    if user_id is not None:
        stmt = stmt.where(InsightJobLog.user_id == user_id)
    result = await db.execute(stmt)
    return sum(
        (estimate_cost_usd(model or "", inp or 0, out or 0) for model, inp, out in result),
        start=0.0,
    )


async def list_activity(db: AsyncSession, user_id: uuid.UUID) -> list[InsightActivityLog]:
    """A user's recent API activity, newest first."""
    result = await db.execute(
        select(InsightActivityLog)
        .where(InsightActivityLog.user_id == user_id)
        .order_by(InsightActivityLog.created_at.desc())
        .limit(_LIST_PAGE_SIZE)
    )
    return list(result.scalars().all())


async def usage_summary(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Per-user counts for the usage endpoint: insights by period, API activity,
    spend and last generation time.
    """
    counts_result = await db.execute(
        select(Insight.period_type, func.count())
        .where(Insight.user_id == user_id)
        .group_by(Insight.period_type)
    )
    generated_by_period: dict[str, int] = dict(counts_result.all())

    activity_count = (
        await db.execute(
            select(func.count()).select_from(InsightActivityLog).where(
                InsightActivityLog.user_id == user_id
            )
        )
    ).scalar_one()

    last_generated_at = (
        await db.execute(
            select(func.max(Insight.created_at)).where(Insight.user_id == user_id)
        )
    ).scalar_one()

    return {
        "total_generated": sum(generated_by_period.values()),
        "generated_by_period": generated_by_period,
        "activity_count": activity_count,
        "spend_usd": await total_spend_usd(db, user_id=user_id),
        "last_generated_at": last_generated_at,
    }
