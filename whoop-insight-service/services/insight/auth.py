"""Per-user authorization: the master API key, or that user's own
`read_token` — the one whoop-service issues at WHOOP-connect time, read
here from its `users` table. One identity across every service.

`users` is a narrow Table on a private MetaData (never Base.metadata), so
this service's migrations can never touch a table it doesn't own — same
pattern as whoop_read.py.
"""

import secrets
import uuid

from fastapi import Depends, Header
from sqlalchemy import Column, MetaData, String, Table, Uuid, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import bearer_token, is_master_key
from core.db import get_db
from core.exceptions import InvalidApiKeyError

_metadata = MetaData()

users = Table(
    "users",
    _metadata,
    Column("id", Uuid),
    Column("read_token", String),
)


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
    result = await db.execute(select(users.c.read_token).where(users.c.id == user_id))
    read_token = result.scalar_one_or_none()
    if read_token is None or not secrets.compare_digest(token, read_token):
        raise InvalidApiKeyError()
