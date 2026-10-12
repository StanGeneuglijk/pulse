"""A fresh async Redis connection per call — every caller (locks, health) is
low-frequency, and nothing is bound to one event loop.
"""

from redis.asyncio import Redis

from core.config import settings


def get_redis_conn() -> Redis:
    """Use as `async with get_redis_conn() as conn:` so it's closed right after."""
    # driver_info=None: no CLIENT SETINFO on connect, two commands fewer
    # per connection against Upstash's command quota (see core/config.py).
    return Redis.from_url(settings.redis_url, protocol=2, driver_info=None)
