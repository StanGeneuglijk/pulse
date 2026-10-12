import uuid

import pytest

from services.nutrition.crud import (
    confirm_meal,
    create_conversation,
    discard_pending_meal,
    get_active_goal,
    set_goal,
    set_pending_meal,
    summarize,
)
from services.nutrition.exceptions import NoPendingMealError
from tests.conftest import sample_meal_proposal


async def test_confirm_meal_raises_without_a_pending_proposal(db_session):
    conversation = await create_conversation(db_session, uuid.uuid4())

    with pytest.raises(NoPendingMealError):
        await confirm_meal(db_session, conversation.id)


async def test_confirm_meal_persists_the_log_and_its_items(db_session):
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, user_id)
    await set_pending_meal(
        db_session, conversation, sample_meal_proposal(), model_name="claude-sonnet-5"
    )

    log = await confirm_meal(db_session, conversation.id)

    assert log.user_id == user_id
    assert log.calories == 450
    assert log.model_name == "claude-sonnet-5"

    await db_session.refresh(conversation)
    assert conversation.pending_meal is None


async def test_discard_pending_meal_raises_without_one(db_session):
    conversation = await create_conversation(db_session, uuid.uuid4())

    with pytest.raises(NoPendingMealError):
        await discard_pending_meal(db_session, conversation.id)


async def test_discard_pending_meal_clears_it(db_session):
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, user_id)
    await set_pending_meal(db_session, conversation, sample_meal_proposal(), model_name="fake")

    await discard_pending_meal(db_session, conversation.id)

    await db_session.refresh(conversation)
    assert conversation.pending_meal is None


async def test_setting_a_new_goal_deactivates_the_previous_one(db_session):
    user_id = uuid.uuid4()
    first = await set_goal(
        db_session,
        user_id,
        goal_type="weight_loss",
        target_calories=1800,
        target_protein_g=140.0,
        target_carbs_g=None,
        target_fat_g=None,
        notes=None,
    )
    second = await set_goal(
        db_session,
        user_id,
        goal_type="maintenance",
        target_calories=2200,
        target_protein_g=None,
        target_carbs_g=None,
        target_fat_g=None,
        notes=None,
    )

    await db_session.refresh(first)
    active = await get_active_goal(db_session, user_id)
    assert first.is_active is False
    assert active.id == second.id


async def test_summarize_computes_totals_and_goal_delta(db_session):
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, user_id)
    await set_pending_meal(db_session, conversation, sample_meal_proposal(), model_name="fake")
    await confirm_meal(db_session, conversation.id)
    await set_goal(
        db_session,
        user_id,
        goal_type="weight_loss",
        target_calories=400,
        target_protein_g=None,
        target_carbs_g=None,
        target_fat_g=None,
        notes=None,
    )

    summary = await summarize(db_session, user_id, "daily")

    assert summary["meal_count"] == 1
    assert summary["total_calories"] == 450
    assert summary["goal_delta"]["target_calories_per_day"] == 400
    assert summary["goal_delta"]["delta_calories_per_day"] == pytest.approx(50.0)
