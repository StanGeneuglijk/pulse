"""Health-check logic, kept out of api/main.py so that file only routes and
maps exceptions."""

from time import monotonic

from sqlalchemy import text

from core.config import REDIS_HEALTH_TTL_SECONDS
from core.db import engine
from core.exceptions import DependencyUnavailableError
from core.redis_client import get_redis_conn

# When Redis last answered a ping (monotonic seconds), or None. A failure
# clears it, so recovery shows up on the very next check.
_redis_ok_at: float | None = None


async def check_health() -> dict:
    """Readiness check: proves Postgres and Redis are both reachable.

    Postgres is queried on every call. A successful Redis ping is reused for
    REDIS_HEALTH_TTL_SECONDS: Render polls this route every ~10 s per service,
    and Upstash's free plan counts every command (see core/config.py).

    Raises:
        DependencyUnavailableError: Naming whichever dependency failed.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise DependencyUnavailableError("database") from exc

    await _check_redis()
    return {"status": "ok"}


async def _check_redis() -> None:
    global _redis_ok_at
    now = monotonic()
    if _redis_ok_at is not None and now - _redis_ok_at < REDIS_HEALTH_TTL_SECONDS:
        return
    try:
        async with get_redis_conn() as conn:
            await conn.ping()
    except Exception as exc:
        _redis_ok_at = None
        raise DependencyUnavailableError("redis") from exc
    _redis_ok_at = now
