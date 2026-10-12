"""Short-lived coordination locks against Redis."""

from core.redis_client import get_redis_conn


async def acquire_lock(key: str, ttl_seconds: int) -> bool:
    """A Redis `SET NX` with a TTL: only the first caller within the window
    wins. The key and TTL are the caller's choice.

    Returns:
        True if this call may proceed; False if the lock is already held.
    """
    async with get_redis_conn() as conn:
        return bool(await conn.set(key, "1", nx=True, ex=ttl_seconds))
