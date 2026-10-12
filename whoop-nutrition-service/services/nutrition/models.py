"""ORM schema owned by this service. A confirmed meal is a plain insert (eating
the same thing twice is two events), unlike whoop-service's upserted records.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.clock import utcnow
from core.db import Base


class NutritionConversation(Base):
    __tablename__ = "nutrition_conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # No ForeignKey: `users` belongs to whoop-service.
    user_id: Mapped[uuid.UUID]
    # The last proposed breakdown, awaiting confirm/discard.
    pending_meal: Mapped[dict | None] = mapped_column(JSONB, default=None)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    __table_args__ = (Index("ix_nutrition_conversations_user_id", "user_id"),)


class NutritionMessage(Base):
    __tablename__ = "nutrition_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("nutrition_conversations.id")
    )
    role: Mapped[str]  # user | assistant
    content: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (Index("ix_nutrition_messages_conversation_id", "conversation_id"),)


class NutritionLog(Base):
    """A confirmed meal — created only by crud.confirm_meal."""

    __tablename__ = "nutrition_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("nutrition_conversations.id"), default=None
    )
    description: Mapped[str]
    logged_at: Mapped[datetime]  # when eaten — Claude-resolved, not necessarily "now"
    calories: Mapped[int]
    protein_g: Mapped[float]
    carbs_g: Mapped[float]
    fat_g: Mapped[float]
    fiber_g: Mapped[float | None]
    sugar_g: Mapped[float | None]
    sodium_mg: Mapped[float | None]
    model_name: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (
        Index("ix_nutrition_logs_user_id", "user_id"),
        Index("ix_nutrition_logs_logged_at", "logged_at"),
    )


class NutritionMealItem(Base):
    __tablename__ = "nutrition_meal_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("nutrition_logs.id"))
    name: Mapped[str]
    quantity: Mapped[str]
    calories: Mapped[int]
    protein_g: Mapped[float]
    carbs_g: Mapped[float]
    fat_g: Mapped[float]

    __table_args__ = (Index("ix_nutrition_meal_items_meal_id", "meal_id"),)


class NutritionGoal(Base):
    """A user's nutrition goal; at most one row per user is active."""

    __tablename__ = "nutrition_goals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]
    goal_type: Mapped[str]  # weight_loss | weight_gain | maintenance | muscle_gain
    target_calories: Mapped[int | None]
    target_protein_g: Mapped[float | None]
    target_carbs_g: Mapped[float | None]
    target_fat_g: Mapped[float | None]
    notes: Mapped[str | None]
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (Index("ix_nutrition_goals_user_id", "user_id"),)


class NutritionJobLog(Base):
    """One row per chat turn or transcription attempt, with its usage (tokens, or
    audio seconds for a transcription) — what the spend cap sums.
    """

    __tablename__ = "nutrition_job_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]
    status: Mapped[str]  # success | failed
    model_name: Mapped[str | None]
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    # Transcriptions only: the unit Whisper bills on.
    audio_seconds: Mapped[float | None] = mapped_column(default=None)
    duration_ms: Mapped[float]
    error_message: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)

    __table_args__ = (Index("ix_nutrition_job_logs_user_id", "user_id"),)


class NutritionActivityLog(Base):
    """One row per API hit, for the usage endpoint."""

    __tablename__ = "nutrition_activity_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]
    route: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)

    __table_args__ = (Index("ix_nutrition_activity_logs_user_id", "user_id"),)
