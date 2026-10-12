"""Per-conversation turn lock (Redis SET NX + TTL): a double-submit can't
interleave two replies or pay for two calls.
"""

import uuid

from core.redis_client import get_redis_conn

_LOCK_KEY_PREFIX = "nutrition_lock:"


async def acquire_conversation_lock(conversation_id: uuid.UUID, *, ttl_seconds: int) -> bool:
    """True if this turn may proceed; False if one is already running."""
    async with get_redis_conn() as conn:
        return bool(
            await conn.set(f"{_LOCK_KEY_PREFIX}{conversation_id}", "1", nx=True, ex=ttl_seconds)
        )


async def release_conversation_lock(conversation_id: uuid.UUID) -> None:
    """Release in the caller's `finally`, rather than waiting out the TTL."""
    async with get_redis_conn() as conn:
        await conn.delete(f"{_LOCK_KEY_PREFIX}{conversation_id}")
