"""Generic, product-agnostic durable logs. Product-specific logging (a sync
job's outcome) lives on that product's own models — see
services/whoop/models.py's SyncJobLog/UserActivityLog.
"""

import uuid
from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from core.clock import utcnow
from core.db import Base


class ErrorLog(Base):
    """One row per domain exception mapped to an HTTP error in api/main.py."""

    __tablename__ = "error_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    exception_type: Mapped[str]
    message: Mapped[str]
    context: Mapped[str | None]  # route path or job name
    user_id: Mapped[uuid.UUID | None]
    # Same id as the request's X-Request-ID header and its stdout log lines.
    request_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
