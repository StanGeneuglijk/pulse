"""HTTP routes for nutrition: auth and a DB session via dependencies; the work
happens in chat.py and crud.py.
"""

import time
import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import require_api_key
from core.clock import utcnow
from core.db import get_db
from services.nutrition.activity_log import log_activity
from services.nutrition.auth import require_conversation_owner, require_user_access
from services.nutrition.chat import handle_turn
from services.nutrition.config import (
    NUTRITION_MAX_AUDIO_BYTES,
    NUTRITION_SPEND_LIMIT_USD,
    NutritionPeriod,
    nutrition_settings,
)
from services.nutrition.crud import (
    confirm_meal,
    discard_pending_meal,
    enforce_spend_cap,
    get_active_goal,
    list_activity,
    list_meals,
    set_goal,
    summarize,
    total_spend_usd,
    usage_summary,
    write_nutrition_job_log,
)
from services.nutrition.exceptions import AudioTooLargeError
from services.nutrition.llm import ChatLLMClient
from services.nutrition.providers import get_llm_client, get_transcription_client
from services.nutrition.schemas import (
    ActivityLogResponse,
    ChatRequest,
    ChatResponse,
    GoalResponse,
    MealProposalResponse,
    NutritionLogResponse,
    SetGoalRequest,
    SpendResponse,
    SummaryResponse,
    UsageResponse,
)
from services.nutrition.transcription import TranscriptionClient

router = APIRouter(prefix="/nutrition", tags=["nutrition"])


@router.post(
    "/chat/{user_id}", response_model=ChatResponse, dependencies=[Depends(require_user_access)]
)
async def chat(
    user_id: uuid.UUID,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    llm_client: ChatLLMClient = Depends(get_llm_client),
) -> ChatResponse:
    conversation, reply, pending_meal = await handle_turn(
        db, llm_client, user_id, body.conversation_id, body.message
    )
    await log_activity(db, user_id, "chat")
    return ChatResponse(
        conversation_id=conversation.id,
        reply=reply,
        pending_meal=MealProposalResponse.model_validate(pending_meal)
        if pending_meal is not None
        else None,
    )


@router.post(
    "/chat/{user_id}/audio",
    response_model=ChatResponse,
    dependencies=[Depends(require_user_access)],
)
async def chat_audio(
    user_id: uuid.UUID,
    audio: UploadFile,
    conversation_id: Annotated[uuid.UUID | None, Form()] = None,
    db: AsyncSession = Depends(get_db),
    llm_client: ChatLLMClient = Depends(get_llm_client),
    transcription_client: TranscriptionClient = Depends(get_transcription_client),
) -> ChatResponse:
    # Checked before transcription too, so a crossed cap can't be exceeded
    # by a transcription plus a chat call in one request.
    await enforce_spend_cap(db, user_id)

    if audio.size is not None and audio.size > NUTRITION_MAX_AUDIO_BYTES:
        raise AudioTooLargeError(NUTRITION_MAX_AUDIO_BYTES)
    audio_bytes = await audio.read(NUTRITION_MAX_AUDIO_BYTES + 1)
    if len(audio_bytes) > NUTRITION_MAX_AUDIO_BYTES:
        raise AudioTooLargeError(NUTRITION_MAX_AUDIO_BYTES)
    content_type = audio.content_type or "audio/webm"
    started_at = time.monotonic()
    try:
        transcription = await transcription_client.transcribe(
            audio_bytes=audio_bytes, content_type=content_type
        )
    except Exception as exc:
        await write_nutrition_job_log(
            db,
            user_id=user_id,
            status="failed",
            duration_ms=(time.monotonic() - started_at) * 1000,
            model_name=nutrition_settings.transcription_model,
            error_message=str(exc),
        )
        raise
    await write_nutrition_job_log(
        db,
        user_id=user_id,
        status="success",
        duration_ms=(time.monotonic() - started_at) * 1000,
        model_name=nutrition_settings.transcription_model,
        audio_seconds=transcription.duration_seconds,
    )
    conversation, reply, pending_meal = await handle_turn(
        db, llm_client, user_id, conversation_id, transcription.text
    )
    await log_activity(db, user_id, "chat_audio")
    return ChatResponse(
        conversation_id=conversation.id,
        reply=reply,
        pending_meal=MealProposalResponse.model_validate(pending_meal)
        if pending_meal is not None
        else None,
        transcript=transcription.text,
    )


@router.post(
    "/meals/confirm/{conversation_id}",
    status_code=201,
    response_model=NutritionLogResponse,
    dependencies=[Depends(require_conversation_owner)],
)
async def confirm(
    conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> NutritionLogResponse:
    log = await confirm_meal(db, conversation_id)
    return NutritionLogResponse.model_validate(log)


@router.post(
    "/meals/discard/{conversation_id}",
    status_code=204,
    dependencies=[Depends(require_conversation_owner)],
)
async def discard(conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    await discard_pending_meal(db, conversation_id)


# Registered before "/meals/{user_id}", which would otherwise capture "summary".
@router.get(
    "/meals/{user_id}/summary",
    response_model=SummaryResponse,
    dependencies=[Depends(require_user_access)],
)
async def meal_summary(
    user_id: uuid.UUID, period: NutritionPeriod = "weekly", db: AsyncSession = Depends(get_db)
) -> SummaryResponse:
    return SummaryResponse(**await summarize(db, user_id, period))


@router.get(
    "/meals/{user_id}",
    response_model=list[NutritionLogResponse],
    dependencies=[Depends(require_user_access)],
)
async def list_for_user(
    user_id: uuid.UUID,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    db: AsyncSession = Depends(get_db),
) -> list[NutritionLogResponse]:
    until = utcnow()
    since = until - timedelta(days=days)
    meals = await list_meals(db, user_id, since=since, until=until)
    await log_activity(db, user_id, "list_meals")
    return [NutritionLogResponse.model_validate(m) for m in meals]


@router.get(
    "/goals/{user_id}",
    response_model=GoalResponse | None,
    dependencies=[Depends(require_user_access)],
)
async def get_goal(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> GoalResponse | None:
    goal = await get_active_goal(db, user_id)
    return GoalResponse.model_validate(goal) if goal is not None else None


@router.put(
    "/goals/{user_id}", response_model=GoalResponse, dependencies=[Depends(require_user_access)]
)
async def put_goal(
    user_id: uuid.UUID, body: SetGoalRequest, db: AsyncSession = Depends(get_db)
) -> GoalResponse:
    goal = await set_goal(
        db,
        user_id,
        goal_type=body.goal_type,
        target_calories=body.target_calories,
        target_protein_g=body.target_protein_g,
        target_carbs_g=body.target_carbs_g,
        target_fat_g=body.target_fat_g,
        notes=body.notes,
    )
    await log_activity(db, user_id, "set_goal")
    return GoalResponse.model_validate(goal)


@router.get("/spend", response_model=SpendResponse, dependencies=[Depends(require_api_key)])
async def spend(db: AsyncSession = Depends(get_db)) -> SpendResponse:
    spent = await total_spend_usd(db)
    return SpendResponse(spent_usd=spent, limit_usd=NUTRITION_SPEND_LIMIT_USD)


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
