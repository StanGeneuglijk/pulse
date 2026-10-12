import uuid
from datetime import datetime, timedelta

from core.db import Base
from services.insight.nutrition_read import _metadata as nutrition_metadata
from services.insight.nutrition_read import fetch_active_goal, fetch_window
from tests.conftest import seed_goal, seed_nutrition_log


def test_nutrition_metadata_is_not_on_base_metadata():
    """Same isolation guarantee test_whoop_read.py already proves for
    whoop-service's tables: Base.metadata.create_all() must never
    attempt to create/alter nutrition_logs/nutrition_goals."""
    base_table_names = set(Base.metadata.tables)
    nutrition_table_names = set(nutrition_metadata.tables)
    assert base_table_names.isdisjoint(nutrition_table_names)
    assert nutrition_table_names == {"nutrition_logs", "nutrition_goals"}


async def test_fetch_window_returns_only_rows_inside_window(db_session, whoop_tables):
    user_id = uuid.uuid4()
    now = datetime(2026, 9, 20, 12, 0, 0)
    await seed_nutrition_log(
        db_session, user_id, calories=450, protein_g=49.0, carbs_g=44.0, fat_g=6.5,
        logged_at=now - timedelta(days=2),
    )
    await seed_nutrition_log(
        db_session, user_id, calories=300, protein_g=20.0, carbs_g=30.0, fat_g=5.0,
        logged_at=now - timedelta(days=10),  # outside the window
    )

    window = await fetch_window(db_session, user_id, since=now - timedelta(days=7), until=now)

    assert [m.calories for m in window.meals] == [450]


async def test_fetch_window_excludes_other_users(db_session, whoop_tables):
    user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    now = datetime(2026, 9, 20, 12, 0, 0)
    await seed_nutrition_log(
        db_session, other_user_id, calories=500, protein_g=30.0, carbs_g=40.0, fat_g=10.0,
        logged_at=now - timedelta(days=1),
    )

    window = await fetch_window(db_session, user_id, since=now - timedelta(days=7), until=now)

    assert window.is_empty()


async def test_fetch_active_goal_returns_none_when_unset(db_session, whoop_tables):
    goal = await fetch_active_goal(db_session, uuid.uuid4())
    assert goal is None


async def test_fetch_active_goal_returns_the_active_one(db_session, whoop_tables):
    user_id = uuid.uuid4()
    await seed_goal(db_session, user_id, goal_type="weight_loss", target_calories=1800)

    goal = await fetch_active_goal(db_session, user_id)

    assert goal is not None
    assert goal.goal_type == "weight_loss"
    assert goal.target_calories == 1800
