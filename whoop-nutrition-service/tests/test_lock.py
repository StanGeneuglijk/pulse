import asyncio
import uuid

from services.nutrition.lock import acquire_conversation_lock, release_conversation_lock


async def test_only_one_concurrent_acquire_succeeds():
    conversation_id = uuid.uuid4()
    try:
        results = await asyncio.gather(
            acquire_conversation_lock(conversation_id, ttl_seconds=30),
            acquire_conversation_lock(conversation_id, ttl_seconds=30),
        )
        assert sorted(results) == [False, True]
    finally:
        await release_conversation_lock(conversation_id)


async def test_release_lets_a_new_acquire_succeed_immediately():
    conversation_id = uuid.uuid4()
    assert await acquire_conversation_lock(conversation_id, ttl_seconds=30) is True
    assert await acquire_conversation_lock(conversation_id, ttl_seconds=30) is False

    await release_conversation_lock(conversation_id)

    assert await acquire_conversation_lock(conversation_id, ttl_seconds=30) is True
    await release_conversation_lock(conversation_id)
