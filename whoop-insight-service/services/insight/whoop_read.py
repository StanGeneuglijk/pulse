"""Read-only access to whoop-service's recoveries/sleeps/workouts tables.

Narrow Tables on a private MetaData (never Base.metadata), naming only the
columns read here — so this service's Alembic can never migrate a table it
doesn't own. whoop-service's models are the source of truth for the schema.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, MetaData, Table, Uuid, select
from sqlalchemy.ext.asyncio import AsyncSession

_metadata = MetaData()

recoveries = Table(
    "recoveries",
    _metadata,
    Column("user_id", Uuid),
    Column("score", Integer),
    Column("recorded_at", DateTime),
)

sleeps = Table(
    "sleeps",
    _metadata,
    Column("user_id", Uuid),
    Column("score", Integer),
    Column("recorded_at", DateTime),
)

workouts = Table(
    "workouts",
    _metadata,
    Column("user_id", Uuid),
    Column("score", Float),  # strain — real 0-21 decimal scale, not an integer
    Column("recorded_at", DateTime),
)


@dataclass(frozen=True)
class WhoopRecord:
    score: int | float | None
    recorded_at: datetime


@dataclass(frozen=True)
class WhoopWindow:
    recovery: list[WhoopRecord]
    sleep: list[WhoopRecord]
    workout: list[WhoopRecord]

    def is_empty(self) -> bool:
        return not (self.recovery or self.sleep or self.workout)


async def fetch_window(
    db: AsyncSession, user_id: uuid.UUID, *, since: datetime, until: datetime
) -> WhoopWindow:
    """Every recovery/sleep/workout row for `user_id` in `[since, until]`."""

    async def _fetch(table: Table) -> list[WhoopRecord]:
        result = await db.execute(
            select(table.c.score, table.c.recorded_at).where(
                table.c.user_id == user_id,
                table.c.recorded_at >= since,
                table.c.recorded_at <= until,
            )
        )
        return [WhoopRecord(score=row.score, recorded_at=row.recorded_at) for row in result]

    return WhoopWindow(
        recovery=await _fetch(recoveries),
        sleep=await _fetch(sleeps),
        workout=await _fetch(workouts),
    )
