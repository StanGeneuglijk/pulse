"""Caller authentication: the `Bearer` header parsing every auth check in
this service shares, and the master-key gate. Distinct from WHOOP OAuth,
which authenticates the account being synced rather than the caller.
"""

import secrets

from fastapi import Header

from core.config import settings
from core.exceptions import InvalidApiKeyError


def bearer_token(authorization: str) -> str:
    """The token from an `Authorization: Bearer <token>` header.

    Raises:
        InvalidApiKeyError: If the header is missing, empty, or not the
            `Bearer` scheme — a bare key without the prefix is rejected too.
    """
    if not authorization.startswith("Bearer "):
        raise InvalidApiKeyError()
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise InvalidApiKeyError()
    return token


def is_master_key(token: str) -> bool:
    return secrets.compare_digest(token, settings.api_key)


async def require_api_key(authorization: str = Header(default="")) -> None:
    """FastAPI dependency: only the master API key gets through.

    Raises:
        InvalidApiKeyError: If the header isn't `Bearer <API_KEY>`.
    """
    if not is_master_key(bearer_token(authorization)):
        raise InvalidApiKeyError()
