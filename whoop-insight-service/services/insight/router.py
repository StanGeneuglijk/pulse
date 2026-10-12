"""HTTP routes for insights: auth and a DB session via dependencies; the work
happens in generate.py and crud.py.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import require_api_key
from core.db import get_db
from services.insight.activity_log import log_activity
from services.insight.auth import require_user_access
from services.insight.config import INSIGHT_SPEND_LIMIT_USD, InsightPeriod
from services.insight.crud import (
    get_latest_insight,
    list_activity,
    list_insights,
    total_spend_usd,
    usage_summary,
)
from services.insight.exceptions import NoInsightFoundError
from services.insight.generate import generate_insight
from services.insight.llm import LLMClient
from services.insight.providers import get_llm_client
from services.insight.schemas import (
    ActivityLogResponse,
    InsightResponse,
    SpendResponse,
    UsageResponse,
)

router = APIRouter(prefix="/insights", tags=["insights"])


@router.post(
    "/generate/{user_id}",
    status_code=201,
    response_model=InsightResponse,
    dependencies=[Depends(require_user_access)],
)
async def generate(
    user_id: uuid.UUID,
    period: InsightPeriod = "weekly",
    db: AsyncSession = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
) -> InsightResponse:
    insight = await generate_insight(db, llm_client, user_id, period)
    await log_activity(db, user_id, f"generate:{period}")
    return InsightResponse.model_validate(insight)


# Registered before "/{user_id}", which would otherwise capture "spend".
@router.get("/spend", response_model=SpendResponse, dependencies=[Depends(require_api_key)])
async def spend(db: AsyncSession = Depends(get_db)) -> SpendResponse:
    spent = await total_spend_usd(db)
    return SpendResponse(spent_usd=spent, limit_usd=INSIGHT_SPEND_LIMIT_USD)


@router.get(
    "/{user_id}", response_model=list[InsightResponse], dependencies=[Depends(require_user_access)]
)
async def list_for_user(
    user_id: uuid.UUID,
    period: InsightPeriod | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[InsightResponse]:
    insights = await list_insights(db, user_id, period_type=period)
    await log_activity(db, user_id, "list")
    return [InsightResponse.model_validate(i) for i in insights]


@router.get(
    "/{user_id}/latest",
    response_model=InsightResponse,
    dependencies=[Depends(require_user_access)],
)
async def latest_for_user(
    user_id: uuid.UUID,
    period: InsightPeriod = "weekly",
    db: AsyncSession = Depends(get_db),
) -> InsightResponse:
    insight = await get_latest_insight(db, user_id, period_type=period)
    if insight is None:
        raise NoInsightFoundError(str(user_id))
    await log_activity(db, user_id, f"latest:{period}")
    return InsightResponse.model_validate(insight)


@router.get(
    "/{user_id}/activity",
    response_model=list[ActivityLogResponse],
    dependencies=[Depends(require_user_access)],
)
async def activity_for_user(
    user_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[ActivityLogResponse]:
    logs = await list_activity(db, user_id)
    return [ActivityLogResponse.model_validate(log) for log in logs]


@router.get(
    "/{user_id}/usage", response_model=UsageResponse, dependencies=[Depends(require_user_access)]
)
async def usage_for_user(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> UsageResponse:
    return UsageResponse(**await usage_summary(db, user_id))
