"""Per-user authorization: the master API key, or that specific user's own
`read_token`. WHOOP-specific because it reads the `User` model.
"""

import secrets
import uuid

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import bearer_token, is_master_key
from core.db import get_db
from core.exceptions import InvalidApiKeyError
from services.whoop.models import User


async def require_user_access(
    user_id: uuid.UUID,
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> None:
    """FastAPI dependency, matched to the route's `user_id` path parameter.

    Raises:
        InvalidApiKeyError: Unless the caller holds the master key or this
            user's own `read_token`.
    """
    token = bearer_token(authorization)
    if is_master_key(token):
        return
    user = await db.get(User, user_id)
    if user is None or user.read_token is None or not secrets.compare_digest(
        token, user.read_token
    ):
        raise InvalidApiKeyError()
