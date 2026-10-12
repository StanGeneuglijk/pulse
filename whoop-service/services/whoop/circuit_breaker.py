"""Redis-backed circuit breaker for WHOOP: after enough consecutive failures
across all jobs, every job fails fast instead of each burning its own retries.
"""

from core.redis_client import get_redis_conn
from services.whoop.config import (
    WHOOP_CIRCUIT_FAILURE_KEY,
    WHOOP_CIRCUIT_THRESHOLD,
    WHOOP_CIRCUIT_TTL_SECONDS,
)
from services.whoop.exceptions import WhoopDegradedError


async def record_success() -> None:
    """Reset the failure count — a recovered WHOOP closes the circuit immediately."""
    async with get_redis_conn() as conn:
        await conn.delete(WHOOP_CIRCUIT_FAILURE_KEY)


async def record_failure() -> None:
    """Count one more consecutive failure; the TTL lets an isolated burst age out."""
    async with get_redis_conn() as conn, conn.pipeline() as pipe:
        pipe.incr(WHOOP_CIRCUIT_FAILURE_KEY)
        pipe.expire(WHOOP_CIRCUIT_FAILURE_KEY, WHOOP_CIRCUIT_TTL_SECONDS)
        await pipe.execute()


async def raise_if_open() -> None:
    """Raises:
        WhoopDegradedError: If consecutive failures reached WHOOP_CIRCUIT_THRESHOLD.
    """
    async with get_redis_conn() as conn:
        count = int(await conn.get(WHOOP_CIRCUIT_FAILURE_KEY) or 0)
    if count >= WHOOP_CIRCUIT_THRESHOLD:
        raise WhoopDegradedError(count)
