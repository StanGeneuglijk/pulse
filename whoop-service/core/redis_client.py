"""A fresh async Redis connection per call, for everything except RQ.

A connection pool created once would be bound to the event loop that
created it, and RQ runs each async job in its own loop — reusing the pool
across jobs hangs. Every caller here is low-frequency, so a new
connection per call is cheap. (core/queue.py's sync connection is RQ's own.)
"""

from redis.asyncio import Redis

from core.config import settings


def get_redis_conn() -> Redis:
    """Use as `async with get_redis_conn() as conn:` so it's closed right after."""
    # driver_info=None: no CLIENT SETINFO on connect, two commands fewer
    # per connection against Upstash's command quota (see core/config.py).
    return Redis.from_url(settings.redis_url, protocol=2, driver_info=None)
