import asyncio
import uuid

from services.insight.lock import acquire_insight_lock, release_insight_lock


async def test_only_one_concurrent_acquire_succeeds():
    user_id = uuid.uuid4()
    try:
        results = await asyncio.gather(
            acquire_insight_lock(user_id, ttl_seconds=30),
            acquire_insight_lock(user_id, ttl_seconds=30),
        )
        assert sorted(results) == [False, True]
    finally:
        await release_insight_lock(user_id)


async def test_release_lets_a_new_acquire_succeed_immediately():
    user_id = uuid.uuid4()
    assert await acquire_insight_lock(user_id, ttl_seconds=30) is True
    assert await acquire_insight_lock(user_id, ttl_seconds=30) is False

    await release_insight_lock(user_id)

    assert await acquire_insight_lock(user_id, ttl_seconds=30) is True
    await release_insight_lock(user_id)


async def test_lock_expires_on_its_own():
    user_id = uuid.uuid4()
    assert await acquire_insight_lock(user_id, ttl_seconds=1) is True
    await asyncio.sleep(1.2)
    assert await acquire_insight_lock(user_id, ttl_seconds=1) is True
    await release_insight_lock(user_id)
