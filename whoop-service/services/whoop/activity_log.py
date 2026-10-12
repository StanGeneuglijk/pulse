"""Records which read routes a user hits (UserActivityLog)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from services.whoop.models import UserActivityLog

logger = get_logger(__name__)


async def log_activity(db: AsyncSession, user_id: uuid.UUID, route: str) -> None:
    """Best-effort: a failed write is logged and swallowed, never failing the request."""
    try:
        db.add(UserActivityLog(user_id=user_id, route=route))
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("activity_log_write_failed")
