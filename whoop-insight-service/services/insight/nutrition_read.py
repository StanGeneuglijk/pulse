"""Read-only access to whoop-nutrition-service's meals and goals — same
private-MetaData pattern as whoop_read.py.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Uuid,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

_metadata = MetaData()

nutrition_logs = Table(
    "nutrition_logs",
    _metadata,
    Column("user_id", Uuid),
    Column("logged_at", DateTime),
    Column("calories", Integer),
    Column("protein_g", Float),
    Column("carbs_g", Float),
    Column("fat_g", Float),
)

nutrition_goals = Table(
    "nutrition_goals",
    _metadata,
    Column("user_id", Uuid),
    Column("goal_type", String),
    Column("target_calories", Integer),
    Column("target_protein_g", Float),
    Column("target_carbs_g", Float),
    Column("target_fat_g", Float),
    Column("is_active", Boolean),
    Column("created_at", DateTime),
)


@dataclass(frozen=True)
class NutritionRecord:
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    logged_at: datetime


@dataclass(frozen=True)
class NutritionWindow:
    meals: list[NutritionRecord]

    def is_empty(self) -> bool:
        return not self.meals


@dataclass(frozen=True)
class ActiveGoal:
    goal_type: str
    target_calories: int | None
    target_protein_g: float | None
    target_carbs_g: float | None
    target_fat_g: float | None


async def fetch_window(
    db: AsyncSession, user_id: uuid.UUID, *, since: datetime, until: datetime
) -> NutritionWindow:
    """Every confirmed meal for `user_id` in `[since, until]`."""
    result = await db.execute(
        select(
            nutrition_logs.c.calories,
            nutrition_logs.c.protein_g,
            nutrition_logs.c.carbs_g,
            nutrition_logs.c.fat_g,
            nutrition_logs.c.logged_at,
        ).where(
            nutrition_logs.c.user_id == user_id,
            nutrition_logs.c.logged_at >= since,
            nutrition_logs.c.logged_at <= until,
        )
    )
    return NutritionWindow(
        meals=[
            NutritionRecord(
                calories=row.calories,
                protein_g=row.protein_g,
                carbs_g=row.carbs_g,
                fat_g=row.fat_g,
                logged_at=row.logged_at,
            )
            for row in result
        ]
    )


async def fetch_active_goal(db: AsyncSession, user_id: uuid.UUID) -> ActiveGoal | None:
    """The user's active goal, if any (at most one is active per user)."""
    result = await db.execute(
        select(
            nutrition_goals.c.goal_type,
            nutrition_goals.c.target_calories,
            nutrition_goals.c.target_protein_g,
            nutrition_goals.c.target_carbs_g,
            nutrition_goals.c.target_fat_g,
        ).where(nutrition_goals.c.user_id == user_id, nutrition_goals.c.is_active.is_(True))
    )
    row = result.first()
    if row is None:
        return None
    return ActiveGoal(
        goal_type=row.goal_type,
        target_calories=row.target_calories,
        target_protein_g=row.target_protein_g,
        target_carbs_g=row.target_carbs_g,
        target_fat_g=row.target_fat_g,
    )
