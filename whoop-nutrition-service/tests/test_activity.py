import uuid

from services.nutrition.activity_log import log_activity
from services.nutrition.crud import (
    confirm_meal,
    create_conversation,
    list_activity,
    set_pending_meal,
    usage_summary,
)
from tests.conftest import sample_meal_proposal


async def test_log_activity_writes_a_row(db_session):
    user_id = uuid.uuid4()

    await log_activity(db_session, user_id, "chat")

    rows = await list_activity(db_session, user_id)
    assert [r.route for r in rows] == ["chat"]


async def test_usage_summary_reflects_a_confirmed_meal(db_session):
    user_id = uuid.uuid4()
    conversation = await create_conversation(db_session, user_id)
    await set_pending_meal(db_session, conversation, sample_meal_proposal(), model_name="fake")
    await confirm_meal(db_session, conversation.id)
    await log_activity(db_session, user_id, "chat")

    summary = await usage_summary(db_session, user_id)

    assert summary["meals_logged"] == 1
    assert summary["conversations_started"] == 1
    assert summary["activity_count"] == 1
    assert summary["last_meal_logged_at"] is not None
