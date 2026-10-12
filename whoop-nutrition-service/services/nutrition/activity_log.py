"""Records which routes a user hits (NutritionActivityLog)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from services.nutrition.models import NutritionActivityLog

logger = get_logger(__name__)


async def log_activity(db: AsyncSession, user_id: uuid.UUID, route: str) -> None:
    """Behavioral record of an API hit — a logging failure here must
    never turn a successful request into a broken response."""
    try:
        db.add(NutritionActivityLog(user_id=user_id, route=route))
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("activity_log_write_failed")
