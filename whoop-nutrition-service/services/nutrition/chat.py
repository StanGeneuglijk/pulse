"""Orchestration for one chat turn: cap -> lock -> history + goal -> LLM ->
store reply -> stage or clear the proposal -> job log.
"""

import time
import uuid
from typing import cast

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from services.nutrition.config import (
    NUTRITION_CHAT_EFFORT,
    NUTRITION_CHAT_MAX_TOKENS,
    NUTRITION_CONTEXT_MESSAGE_LIMIT,
    NUTRITION_LOCK_TTL_SECONDS,
)
from services.nutrition.crud import (
    add_message,
    create_conversation,
    enforce_spend_cap,
    get_active_goal,
    get_conversation,
    list_recent_messages,
    set_pending_meal,
    write_nutrition_job_log,
)
from services.nutrition.exceptions import ConversationLockedError
from services.nutrition.llm import ChatLLMClient, ChatMessage, MealProposal, Role
from services.nutrition.lock import acquire_conversation_lock, release_conversation_lock
from services.nutrition.models import NutritionConversation
from services.nutrition.prompt import build_system_prompt

logger = get_logger(__name__)


async def handle_turn(
    db: AsyncSession,
    llm_client: ChatLLMClient,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    message: str,
) -> tuple[NutritionConversation, str | None, MealProposal | None]:
    """Run one turn, creating the conversation when `conversation_id` is None.
    Returns `(conversation, reply_text, pending_meal)`.

    Raises:
        SpendLimitExceededError: Per-user or platform cap reached (checked first).
        ConversationLockedError: A turn is already running for this conversation.
        LLMProviderError: The provider call failed.
    """
    await enforce_spend_cap(db, user_id)

    conversation = (
        await create_conversation(db, user_id)
        if conversation_id is None
        else await get_conversation(db, conversation_id)
    )

    # A rollback expires ORM attributes, so `finally` must not touch conversation.id.
    conversation_id_value = conversation.id

    if not await acquire_conversation_lock(
        conversation_id_value, ttl_seconds=NUTRITION_LOCK_TTL_SECONDS
    ):
        raise ConversationLockedError(str(conversation_id_value))

    structlog.contextvars.bind_contextvars(
        user_id=str(user_id), conversation_id=str(conversation_id_value)
    )
    started_at = time.monotonic()
    try:
        logger.info("chat_turn_started")
        await add_message(db, conversation_id_value, "user", message)

        history = await list_recent_messages(
            db, conversation_id_value, limit=NUTRITION_CONTEXT_MESSAGE_LIMIT
        )
        active_goal = await get_active_goal(db, user_id)
        system = build_system_prompt(active_goal=active_goal)
        # add_message only ever writes "user"/"assistant", so the cast is safe.
        chat_messages = [
            ChatMessage(role=cast(Role, m.role), content=m.content) for m in history
        ]

        # End the read transaction before the slow LLM call, so a pooled
        # database connection isn't held idle for its whole duration.
        await db.commit()

        result = await llm_client.send(
            system=system,
            messages=chat_messages,
            max_tokens=NUTRITION_CHAT_MAX_TOKENS,
            effort=NUTRITION_CHAT_EFFORT,
        )

        reply_text = result.text or (
            "Here's what I've got — take a look below." if result.tool_call else None
        )
        if reply_text is not None:
            await add_message(db, conversation_id_value, "assistant", reply_text)
        await set_pending_meal(db, conversation, result.tool_call, model_name=result.model)

        logger.info("chat_turn_complete", proposed_meal=result.tool_call is not None)
        await write_nutrition_job_log(
            db,
            user_id=user_id,
            status="success",
            duration_ms=(time.monotonic() - started_at) * 1000,
            model_name=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
        return conversation, reply_text, result.tool_call
    except Exception as exc:
        logger.exception("chat_turn_failed")
        await db.rollback()
        await write_nutrition_job_log(
            db,
            user_id=user_id,
            status="failed",
            duration_ms=(time.monotonic() - started_at) * 1000,
            error_message=str(exc),
        )
        raise
    finally:
        await release_conversation_lock(conversation_id_value)
        structlog.contextvars.clear_contextvars()
