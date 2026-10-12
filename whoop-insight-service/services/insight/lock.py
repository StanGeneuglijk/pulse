"""Per-user generation lock (Redis SET NX + TTL): a double-click or client retry
never pays for a second LLM call while the first is running.
"""

import uuid

from core.redis_client import get_redis_conn

_LOCK_KEY_PREFIX = "insight_lock:"


async def acquire_insight_lock(user_id: uuid.UUID, *, ttl_seconds: int) -> bool:
    """True if this call may proceed; False if a generation is already running."""
    async with get_redis_conn() as conn:
        return bool(
            await conn.set(f"{_LOCK_KEY_PREFIX}{user_id}", "1", nx=True, ex=ttl_seconds)
        )


async def release_insight_lock(user_id: uuid.UUID) -> None:
    """Release in the caller's `finally`, rather than waiting out the TTL."""
    async with get_redis_conn() as conn:
        await conn.delete(f"{_LOCK_KEY_PREFIX}{user_id}")
