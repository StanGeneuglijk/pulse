"""ORM schema owned by this service. Insights are written only through
crud.upsert_insight. Other services' tables are read via whoop_read.py and
nutrition_read.py, never mapped here.
"""

import uuid
from datetime import datetime

from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.clock import utcnow
from core.db import Base


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # No ForeignKey: `users` belongs to whoop-service.
    user_id: Mapped[uuid.UUID]
    period_type: Mapped[str]  # daily | weekly | monthly — see config.py's PERIOD_POLICY
    period_start: Mapped[datetime]
    period_end: Mapped[datetime]
    prompt_version: Mapped[str]
    model_name: Mapped[str]
    content: Mapped[str]
    content_hash: Mapped[str]  # see crud.content_hash
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "period_type",
            "period_start",
            "period_end",
            "prompt_version",
            name="uq_user_insight_period",
        ),
        Index("ix_insights_user_id", "user_id"),
    )


class InsightJobLog(Base):
    """One row per generation attempt, with token usage — what the spend cap sums.
    No foreign key on `user_id`, so an attempt for an unknown user still logs.
    """

    __tablename__ = "insight_job_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]
    status: Mapped[str]  # success | failed
    period_type: Mapped[str]  # daily | weekly | monthly
    model_name: Mapped[str | None]
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    duration_ms: Mapped[float]
    error_message: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)

    __table_args__ = (Index("ix_insight_job_logs_user_id", "user_id"),)


class InsightActivityLog(Base):
    """One row per API hit — how people use the service, for the usage endpoint."""

    __tablename__ = "insight_activity_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]
    route: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)

    __table_args__ = (Index("ix_insight_activity_logs_user_id", "user_id"),)
