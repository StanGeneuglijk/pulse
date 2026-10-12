import uuid
from datetime import datetime, timedelta

from core.db import Base
from services.insight.whoop_read import _metadata as whoop_metadata
from services.insight.whoop_read import fetch_window
from tests.conftest import seed_recovery, seed_sleep, seed_workout


def test_whoop_metadata_is_not_on_base_metadata():
    """task 3's acceptance: Base.metadata.create_all() must never attempt
    to create/alter recoveries/sleeps/workouts — proven by the two
    MetaData objects not sharing a single table."""
    base_table_names = set(Base.metadata.tables)
    whoop_table_names = set(whoop_metadata.tables)
    assert base_table_names.isdisjoint(whoop_table_names)
    assert whoop_table_names == {"recoveries", "sleeps", "workouts"}


async def test_fetch_window_returns_only_rows_inside_window(db_session, whoop_tables):
    user_id = uuid.uuid4()
    now = datetime(2026, 9, 20, 12, 0, 0)
    await seed_recovery(db_session, user_id, 80, now - timedelta(days=2))  # inside
    await seed_recovery(db_session, user_id, 40, now - timedelta(days=10))  # outside
    await seed_sleep(db_session, user_id, 70, now - timedelta(days=1))  # inside
    await seed_workout(db_session, user_id, 12.5, now - timedelta(days=3))  # inside

    window = await fetch_window(db_session, user_id, since=now - timedelta(days=7), until=now)

    assert [r.score for r in window.recovery] == [80]
    assert [r.score for r in window.sleep] == [70]
    assert [r.score for r in window.workout] == [12.5]


async def test_fetch_window_excludes_other_users(db_session, whoop_tables):
    user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    now = datetime(2026, 9, 20, 12, 0, 0)
    await seed_recovery(db_session, other_user_id, 90, now - timedelta(days=1))

    window = await fetch_window(db_session, user_id, since=now - timedelta(days=7), until=now)

    assert window.is_empty()
