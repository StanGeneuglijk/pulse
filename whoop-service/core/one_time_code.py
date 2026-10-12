"""Redis-backed one-time code -> payload handoff: how a freshly issued
`read_token` reaches the frontend without ever appearing in a URL.
"""

import json
import secrets

from core.redis_client import get_redis_conn


class OneTimeCodeStore:
    """One code per handoff; `consume` is a single GETDEL, so a code works once."""

    def __init__(self, key_prefix: str, ttl_seconds: int) -> None:
        self._key_prefix = key_prefix
        self._ttl_seconds = ttl_seconds

    async def create(self, payload: dict) -> str:
        """Mint a code holding `payload`; it expires if never redeemed."""
        code = secrets.token_urlsafe(32)
        async with get_redis_conn() as conn:
            await conn.set(f"{self._key_prefix}{code}", json.dumps(payload), ex=self._ttl_seconds)
        return code

    async def consume(self, code: str) -> dict | None:
        """The payload, or None if the code is unknown, used or expired."""
        async with get_redis_conn() as conn:
            raw = await conn.getdel(f"{self._key_prefix}{code}")
        return json.loads(raw) if raw is not None else None
