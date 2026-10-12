"""Persistence for nutrition: conversations and messages, the confirm/discard
state machine, goals, job/activity logs and spend.
"""

import dataclasses
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.clock import utcnow
from services.nutrition.config import (
    NUTRITION_PER_USER_SPEND_LIMIT_USD,
    NUTRITION_PERIOD_WINDOW_DAYS,
    NUTRITION_SPEND_LIMIT_USD,
    NutritionPeriod,
)
from services.nutrition.exceptions import (
    ConversationNotFoundError,
    NoPendingMealError,
    SpendLimitExceededError,
)
from services.nutrition.llm import MealProposal
from services.nutrition.models import (
    NutritionActivityLog,
    NutritionConversation,
    NutritionGoal,
    NutritionJobLog,
    NutritionLog,
    NutritionMealItem,
    NutritionMessage,
)
from services.nutrition.pricing import (
    WHISPER_PRICE_PER_MINUTE_USD,
    estimate_cost_usd,
    estimate_transcription_cost_usd,
)

_LIST_PAGE_SIZE = 50


async def get_conversation(db: AsyncSession, conversation_id: uuid.UUID) -> NutritionConversation:
    conversation = await db.get(NutritionConversation, conversation_id)
    if conversation is None:
        raise ConversationNotFoundError(str(conversation_id))
    return conversation


async def create_conversation(db: AsyncSession, user_id: uuid.UUID) -> NutritionConversation:
    conversation = NutritionConversation(user_id=user_id)
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def list_recent_messages(
    db: AsyncSession, conversation_id: uuid.UUID, *, limit: int
) -> list[NutritionMessage]:
    """The conversation's most recent `limit` messages, oldest first — the
    bounded context resent on every turn.
    """
    result = await db.execute(
        select(NutritionMessage)
        .where(NutritionMessage.conversation_id == conversation_id)
        .order_by(NutritionMessage.created_at.desc())
        .limit(limit)
    )
    return list(reversed(result.scalars().all()))


async def add_message(
    db: AsyncSession, conversation_id: uuid.UUID, role: str, content: str
) -> NutritionMessage:
    message = NutritionMessage(conversation_id=conversation_id, role=role, content=content)
    db.add(message)
    await db.commit()
    return message


async def set_pending_meal(
    db: AsyncSession,
    conversation: NutritionConversation,
    meal: MealProposal | None,
    *,
    model_name: str | None = None,
) -> None:
    """Stage (or clear) the proposal, with the model that made it for provenance."""
    if meal is None:
        conversation.pending_meal = None
    else:
        conversation.pending_meal = {**dataclasses.asdict(meal), "model_name": model_name}
    await db.commit()


async def confirm_meal(db: AsyncSession, conversation_id: uuid.UUID) -> NutritionLog:
    """Save the staged proposal as a NutritionLog plus item rows and clear it,
    in one transaction.

    Raises:
        NoPendingMealError: If nothing is staged.
    """
    conversation = await get_conversation(db, conversation_id)
    pending = conversation.pending_meal
    if pending is None:
        raise NoPendingMealError(str(conversation_id))

    log = NutritionLog(
        user_id=conversation.user_id,
        conversation_id=conversation_id,
        description=pending["description"],
        logged_at=datetime.fromisoformat(pending["logged_at"]),  # naive UTC, see anthropic_client
        calories=pending["total_calories"],
        protein_g=pending["total_protein_g"],
        carbs_g=pending["total_carbs_g"],
        fat_g=pending["total_fat_g"],
        fiber_g=pending.get("fiber_g"),
        sugar_g=pending.get("sugar_g"),
        sodium_mg=pending.get("sodium_mg"),
        model_name=pending.get("model_name", "unknown"),
    )
    db.add(log)
    await db.flush()  # populate log.id for the child rows below, same transaction

    for item in pending["items"]:
        db.add(
            NutritionMealItem(
                meal_id=log.id,
                name=item["name"],
                quantity=item["quantity"],
                calories=item["calories"],
                protein_g=item["protein_g"],
                carbs_g=item["carbs_g"],
                fat_g=item["fat_g"],
            )
        )

    conversation.pending_meal = None
    await db.commit()
    await db.refresh(log)
    return log


async def discard_pending_meal(db: AsyncSession, conversation_id: uuid.UUID) -> None:
    conversation = await get_conversation(db, conversation_id)
    if conversation.pending_meal is None:
        raise NoPendingMealError(str(conversation_id))
    conversation.pending_meal = None
    await db.commit()


async def list_meals(
    db: AsyncSession, user_id: uuid.UUID, *, since: datetime, until: datetime
) -> list[NutritionLog]:
    result = await db.execute(
        select(NutritionLog).where(
            NutritionLog.user_id == user_id,
            NutritionLog.logged_at >= since,
            NutritionLog.logged_at <= until,
        )
    )
    return list(result.scalars().all())


async def summarize(db: AsyncSession, user_id: uuid.UUID, period: NutritionPeriod) -> dict:
    """Totals for `period`'s window, plus the delta against the active goal."""
    until = utcnow()
    since = until - timedelta(days=NUTRITION_PERIOD_WINDOW_DAYS[period])
    meals = await list_meals(db, user_id, since=since, until=until)

    days = max(NUTRITION_PERIOD_WINDOW_DAYS[period], 1)
    total_calories = sum(m.calories for m in meals)
    total_protein_g = sum(m.protein_g for m in meals)
    total_carbs_g = sum(m.carbs_g for m in meals)
    total_fat_g = sum(m.fat_g for m in meals)

    goal = await get_active_goal(db, user_id)
    goal_delta = None
    if goal is not None and goal.target_calories is not None:
        avg_calories_per_day = total_calories / days
        goal_delta = {
            "target_calories_per_day": goal.target_calories,
            "avg_calories_per_day": avg_calories_per_day,
            "delta_calories_per_day": avg_calories_per_day - goal.target_calories,
        }

    return {
        "period": period,
        "meal_count": len(meals),
        "total_calories": total_calories,
        "avg_calories_per_day": total_calories / days,
        "total_protein_g": total_protein_g,
        "total_carbs_g": total_carbs_g,
        "total_fat_g": total_fat_g,
        "goal_delta": goal_delta,
    }


async def get_active_goal(db: AsyncSession, user_id: uuid.UUID) -> NutritionGoal | None:
    result = await db.execute(
        select(NutritionGoal)
        .where(NutritionGoal.user_id == user_id, NutritionGoal.is_active.is_(True))
        .order_by(NutritionGoal.created_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def set_goal(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    goal_type: str,
    target_calories: int | None,
    target_protein_g: float | None,
    target_carbs_g: float | None,
    target_fat_g: float | None,
    notes: str | None,
) -> NutritionGoal:
    """Deactivate the current goal and create the new active one, in one transaction."""
    previous = await get_active_goal(db, user_id)
    if previous is not None:
        previous.is_active = False

    goal = NutritionGoal(
        user_id=user_id,
        goal_type=goal_type,
        target_calories=target_calories,
        target_protein_g=target_protein_g,
        target_carbs_g=target_carbs_g,
        target_fat_g=target_fat_g,
        notes=notes,
        is_active=True,
    )
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return goal


async def write_nutrition_job_log(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    status: str,
    duration_ms: float,
    model_name: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    audio_seconds: float | None = None,
    error_message: str | None = None,
) -> None:
    """Record one chat turn or transcription attempt; commits on its own."""
    db.add(
        NutritionJobLog(
            user_id=user_id,
            status=status,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            audio_seconds=audio_seconds,
            duration_ms=duration_ms,
            error_message=error_message,
        )
    )
    await db.commit()


async def total_spend_usd(db: AsyncSession, *, user_id: uuid.UUID | None = None) -> float:
    """Estimated cumulative spend over every successful chat turn and
    transcription, across all users or for one — one cap covers both
    vendors. Usage is summed per model in SQL, so this stays one small
    query however long the log grows."""
    stmt = (
        select(
            NutritionJobLog.model_name,
            func.coalesce(func.sum(NutritionJobLog.input_tokens), 0),
            func.coalesce(func.sum(NutritionJobLog.output_tokens), 0),
            func.coalesce(func.sum(NutritionJobLog.audio_seconds), 0.0),
        )
        .where(NutritionJobLog.status == "success", NutritionJobLog.model_name.is_not(None))
        .group_by(NutritionJobLog.model_name)
    )
    if user_id is not None:
        stmt = stmt.where(NutritionJobLog.user_id == user_id)
    result = await db.execute(stmt)
    total = 0.0
    for model_name, input_tokens, output_tokens, audio_seconds in result:
        if model_name in WHISPER_PRICE_PER_MINUTE_USD:
            total += estimate_transcription_cost_usd(model_name, audio_seconds or 0.0)
        else:
            total += estimate_cost_usd(model_name or "", input_tokens or 0, output_tokens or 0)
    return total


async def enforce_spend_cap(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Raise before any paid call once the per-user cap, then the platform cap,
    is reached. Used before both chat and transcription.
    """
    user_spent = await total_spend_usd(db, user_id=user_id)
    if user_spent >= NUTRITION_PER_USER_SPEND_LIMIT_USD:
        raise SpendLimitExceededError(user_spent, NUTRITION_PER_USER_SPEND_LIMIT_USD)

    spent = await total_spend_usd(db)
    if spent >= NUTRITION_SPEND_LIMIT_USD:
        raise SpendLimitExceededError(spent, NUTRITION_SPEND_LIMIT_USD)


async def list_activity(db: AsyncSession, user_id: uuid.UUID) -> list[NutritionActivityLog]:
    result = await db.execute(
        select(NutritionActivityLog)
        .where(NutritionActivityLog.user_id == user_id)
        .order_by(NutritionActivityLog.created_at.desc())
        .limit(_LIST_PAGE_SIZE)
    )
    return list(result.scalars().all())


async def usage_summary(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Per-user counts for the usage endpoint."""
    meals_logged = (
        await db.execute(
            select(func.count()).select_from(NutritionLog).where(NutritionLog.user_id == user_id)
        )
    ).scalar_one()

    conversations_started = (
        await db.execute(
            select(func.count())
            .select_from(NutritionConversation)
            .where(NutritionConversation.user_id == user_id)
        )
    ).scalar_one()

    activity_count = (
        await db.execute(
            select(func.count())
            .select_from(NutritionActivityLog)
            .where(NutritionActivityLog.user_id == user_id)
        )
    ).scalar_one()

    last_meal_logged_at = (
        await db.execute(
            select(func.max(NutritionLog.logged_at)).where(NutritionLog.user_id == user_id)
        )
    ).scalar_one()

    return {
        "meals_logged": meals_logged,
        "conversations_started": conversations_started,
        "activity_count": activity_count,
        "spend_usd": await total_spend_usd(db, user_id=user_id),
        "last_meal_logged_at": last_meal_logged_at,
    }
