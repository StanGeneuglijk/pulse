"""Per-user authorization: the master API key, or the user's own `read_token`
(issued by whoop-service, read from its `users` table via a private MetaData).

Confirm/discard routes are keyed by conversation, not user, so
`require_conversation_owner` resolves the caller from their token first and
only then checks ownership — an unknown token can't probe which ids exist.
"""

import secrets
import uuid

from fastapi import Depends, Header
from sqlalchemy import Column, MetaData, String, Table, Uuid, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import bearer_token, is_master_key
from core.db import get_db
from core.exceptions import InvalidApiKeyError
from services.nutrition.crud import get_conversation

_metadata = MetaData()

users = Table(
    "users",
    _metadata,
    Column("id", Uuid),
    Column("read_token", String),
)


async def _authorized_for_user(provided: str, user_id: uuid.UUID, db: AsyncSession) -> bool:
    if is_master_key(provided):
        return True
    result = await db.execute(select(users.c.read_token).where(users.c.id == user_id))
    read_token = result.scalar_one_or_none()
    return read_token is not None and secrets.compare_digest(provided, read_token)


async def require_user_access(
    user_id: uuid.UUID,
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> None:
    """FastAPI dependency, matched to the route's `user_id` path parameter."""
    provided = bearer_token(authorization)
    if not await _authorized_for_user(provided, user_id, db):
        raise InvalidApiKeyError()


async def require_conversation_owner(
    conversation_id: uuid.UUID,
    authorization: str = Header(default=""),
    db: AsyncSession = Depends(get_db),
) -> None:
    """FastAPI dependency: the master key, or the read_token of the user who owns
    this conversation.
    """
    provided = bearer_token(authorization)
    if is_master_key(provided):
        return

    result = await db.execute(select(users.c.id).where(users.c.read_token == provided))
    caller_user_id = result.scalar_one_or_none()
    if caller_user_id is None:
        raise InvalidApiKeyError()

    conversation = await get_conversation(db, conversation_id)  # raises ConversationNotFoundError
    if conversation.user_id != caller_user_id:
        raise InvalidApiKeyError()
