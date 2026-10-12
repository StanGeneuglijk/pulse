"""Request/response shapes: snake_case in Python, camelCase on the wire."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from services.nutrition.config import NUTRITION_MAX_MESSAGE_CHARS


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class ChatRequest(CamelModel):
    conversation_id: uuid.UUID | None = None
    message: str = Field(min_length=1, max_length=NUTRITION_MAX_MESSAGE_CHARS)


class MealItemResponse(CamelModel):
    name: str
    quantity: str
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float


class MealProposalResponse(CamelModel):
    description: str
    logged_at: str
    items: list[MealItemResponse]
    total_calories: int
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
    fiber_g: float | None = None
    sugar_g: float | None = None
    sodium_mg: float | None = None


class ChatResponse(CamelModel):
    conversation_id: uuid.UUID
    reply: str | None
    pending_meal: MealProposalResponse | None
    transcript: str | None = None  # set only by the audio route


class NutritionLogResponse(CamelModel):
    id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: uuid.UUID | None
    description: str
    logged_at: datetime
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None
    sugar_g: float | None
    sodium_mg: float | None
    model_name: str
    created_at: datetime


class GoalDeltaResponse(CamelModel):
    target_calories_per_day: int
    avg_calories_per_day: float
    delta_calories_per_day: float


class SummaryResponse(CamelModel):
    period: str
    meal_count: int
    total_calories: int
    avg_calories_per_day: float
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
    goal_delta: GoalDeltaResponse | None


class SetGoalRequest(CamelModel):
    goal_type: str
    target_calories: int | None = None
    target_protein_g: float | None = None
    target_carbs_g: float | None = None
    target_fat_g: float | None = None
    notes: str | None = None


class GoalResponse(CamelModel):
    id: uuid.UUID
    user_id: uuid.UUID
    goal_type: str
    target_calories: int | None
    target_protein_g: float | None
    target_carbs_g: float | None
    target_fat_g: float | None
    notes: str | None
    is_active: bool
    created_at: datetime


class SpendResponse(CamelModel):
    spent_usd: float
    limit_usd: float


class ActivityLogResponse(CamelModel):
    route: str
    created_at: datetime


class UsageResponse(CamelModel):
    meals_logged: int
    conversations_started: int
    activity_count: int
    spend_usd: float
    last_meal_logged_at: datetime | None
