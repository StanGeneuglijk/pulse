import uuid

import pytest
from sqlalchemy import select

from services.nutrition.chat import handle_turn
from services.nutrition.config import NUTRITION_SPEND_LIMIT_USD
from services.nutrition.crud import write_nutrition_job_log
from services.nutrition.exceptions import (
    ConversationLockedError,
    LLMProviderError,
    SpendLimitExceededError,
)
from services.nutrition.lock import acquire_conversation_lock, release_conversation_lock
from services.nutrition.models import NutritionJobLog, NutritionMessage
from tests.conftest import FakeChatLLMClient, sample_meal_proposal


async def test_handle_turn_with_a_tool_call_stages_the_pending_meal(db_session):
    user_id = uuid.uuid4()
    fake = FakeChatLLMClient(text="Here's what I calculated:", tool_call=sample_meal_proposal())

    conversation, reply, pending = await handle_turn(db_session, fake, user_id, None, "two eggs")

    assert reply == "Here's what I calculated:"
    assert pending is not None
    assert pending.total_calories == 450
    await db_session.refresh(conversation)
    assert conversation.pending_meal is not None

    messages = (
        await db_session.execute(
            select(NutritionMessage).where(NutritionMessage.conversation_id == conversation.id)
        )
    ).scalars().all()
    assert [m.role for m in messages] == ["user", "assistant"]


async def test_handle_turn_with_text_only_leaves_pending_meal_null(db_session):
    user_id = uuid.uuid4()
    fake = FakeChatLLMClient(text="What size portion was that?")

    conversation, reply, pending = await handle_turn(
        db_session, fake, user_id, None, "I had a burrito"
    )

    assert reply == "What size portion was that?"
    assert pending is None
    await db_session.refresh(conversation)
    assert conversation.pending_meal is None


async def test_handle_turn_reuses_an_existing_conversation(db_session):
    user_id = uuid.uuid4()
    fake = FakeChatLLMClient(text="ok")
    conversation, _, _ = await handle_turn(db_session, fake, user_id, None, "hi")

    conversation2, _, _ = await handle_turn(
        db_session, fake, user_id, conversation.id, "second message"
    )

    assert conversation2.id == conversation.id
    assert fake.calls == 2


async def test_handle_turn_rejects_when_conversation_is_locked(db_session):
    user_id = uuid.uuid4()
    fake = FakeChatLLMClient(text="ok")
    conversation, _, _ = await handle_turn(db_session, fake, user_id, None, "hi")

    assert await acquire_conversation_lock(conversation.id, ttl_seconds=30) is True
    try:
        with pytest.raises(ConversationLockedError):
            await handle_turn(db_session, fake, user_id, conversation.id, "second")
    finally:
        await release_conversation_lock(conversation.id)


async def test_handle_turn_refuses_once_spend_cap_is_reached(db_session):
    user_id = uuid.uuid4()
    over_cap_tokens = int(NUTRITION_SPEND_LIMIT_USD / (10.00 / 1_000_000)) + 1_000
    await write_nutrition_job_log(
        db_session,
        user_id=uuid.uuid4(),
        status="success",
        model_name="claude-sonnet-5",
        input_tokens=0,
        output_tokens=over_cap_tokens,
        duration_ms=1.0,
    )
    fake = FakeChatLLMClient(text="ok")

    with pytest.raises(SpendLimitExceededError):
        await handle_turn(db_session, fake, user_id, None, "hi")

    assert fake.calls == 0


async def test_handle_turn_logs_a_failed_attempt(db_session):
    user_id = uuid.uuid4()

    class FailingClient:
        async def send(self, **kwargs):
            raise LLMProviderError("upstream 529")

    with pytest.raises(LLMProviderError):
        await handle_turn(db_session, FailingClient(), user_id, None, "hi")

    logs = (
        await db_session.execute(select(NutritionJobLog).where(NutritionJobLog.user_id == user_id))
    ).scalars().all()
    assert logs[0].status == "failed"
