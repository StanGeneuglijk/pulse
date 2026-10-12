"""Redis-backed OAuth `state` (CSRF) carrying the login's PKCE verifier, so any
API instance can complete a login another instance started.
"""

from core.redis_client import get_redis_conn


class OAuthStateStore:
    """One state per in-flight login; key prefix and TTL are the caller's choice."""

    def __init__(self, key_prefix: str, ttl_seconds: int) -> None:
        self._key_prefix = key_prefix
        self._ttl_seconds = ttl_seconds

    async def create(self, state: str, code_verifier: str) -> None:
        """Record a state and its PKCE verifier; expires if the login is abandoned."""
        async with get_redis_conn() as conn:
            await conn.set(
                f"{self._key_prefix}{state}", code_verifier, ex=self._ttl_seconds
            )

    async def consume(self, state: str) -> str | None:
        """Atomically fetch-and-delete (GETDEL), so a state works once.

        Returns:
            The PKCE verifier, or None if the state is unknown, used or expired.
        """
        async with get_redis_conn() as conn:
            raw = await conn.getdel(f"{self._key_prefix}{state}")
        # No decode_responses on the connection, so a hit comes back as bytes.
        return raw.decode() if isinstance(raw, bytes) else raw
