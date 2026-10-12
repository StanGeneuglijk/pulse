import uuid
from datetime import datetime

from services.insight.crud import content_hash, upsert_insight
from services.insight.whoop_read import WhoopRecord, WhoopWindow


def _window(score: int) -> WhoopWindow:
    return WhoopWindow(
        recovery=[WhoopRecord(score=score, recorded_at=datetime(2026, 9, 20))],
        sleep=[],
        workout=[],
    )


async def test_upsert_is_idempotent_on_unchanged_content_hash(db_session):
    user_id = uuid.uuid4()
    period_start = datetime(2026, 9, 13)
    period_end = datetime(2026, 9, 20)
    window = _window(80)
    chash = content_hash(window, "v1")

    first = await upsert_insight(
        db_session,
        user_id=user_id,
        period_type="weekly",
        period_start=period_start,
        period_end=period_end,
        prompt_version="v1",
        model_name="fake-model",
        content="first generation",
        content_hash_value=chash,
    )
    second = await upsert_insight(
        db_session,
        user_id=user_id,
        period_type="weekly",
        period_start=period_start,
        period_end=period_end,
        prompt_version="v1",
        model_name="fake-model",
        content="a different generation the where= clause should suppress",
        content_hash_value=chash,
    )

    assert first.id == second.id
    assert second.content == "first generation"  # the second write never happened


async def test_upsert_overwrites_when_content_hash_changes(db_session):
    user_id = uuid.uuid4()
    period_start = datetime(2026, 9, 13)
    period_end = datetime(2026, 9, 20)

    first = await upsert_insight(
        db_session,
        user_id=user_id,
        period_type="weekly",
        period_start=period_start,
        period_end=period_end,
        prompt_version="v1",
        model_name="fake-model",
        content="stale insight",
        content_hash_value=content_hash(_window(80), "v1"),
    )
    second = await upsert_insight(
        db_session,
        user_id=user_id,
        period_type="weekly",
        period_start=period_start,
        period_end=period_end,
        prompt_version="v1",
        model_name="fake-model",
        content="fresh insight, new underlying data",
        content_hash_value=content_hash(_window(40), "v1"),
    )

    assert first.id == second.id  # same key, updated in place
    assert second.content == "fresh insight, new underlying data"


def test_content_hash_is_stable_and_prompt_version_sensitive():
    window = _window(80)
    assert content_hash(window, "v1") == content_hash(window, "v1")
    assert content_hash(window, "v1") != content_hash(window, "v2")
    assert content_hash(window, "v1") != content_hash(_window(40), "v1")
