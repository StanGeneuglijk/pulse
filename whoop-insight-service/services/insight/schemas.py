"""Response shapes: snake_case in Python, camelCase on the wire."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


class InsightResponse(CamelModel):
    id: uuid.UUID
    user_id: uuid.UUID
    period_type: str
    period_start: datetime
    period_end: datetime
    prompt_version: str
    model_name: str
    content: str
    created_at: datetime


class SpendResponse(CamelModel):
    spent_usd: float
    limit_usd: float


class ActivityLogResponse(CamelModel):
    route: str
    created_at: datetime


class UsageResponse(CamelModel):
    total_generated: int
    generated_by_period: dict[str, int]
    activity_count: int
    spend_usd: float
    last_generated_at: datetime | None
