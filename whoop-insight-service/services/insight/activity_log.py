"""Records which routes a user hits (InsightActivityLog)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from services.insight.models import InsightActivityLog

logger = get_logger(__name__)


async def log_activity(db: AsyncSession, user_id: uuid.UUID, route: str) -> None:
    """Best-effort: a failed write is logged and swallowed, never failing the request."""
    try:
        db.add(InsightActivityLog(user_id=user_id, route=route))
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("activity_log_write_failed")
