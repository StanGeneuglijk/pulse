"""Request correlation and the ErrorLog write every exception handler in
api/main.py shares.

Request logs go to stdout (structured, see core/logging.py) rather than a
table: the host already keeps and searches them, and a row per request
turned out to be ~90% health-check noise. Only domain errors are persisted.
"""

import time
import uuid

import structlog
from fastapi import Request

from core.db import async_session_factory
from core.log_models import ErrorLog
from core.logging import get_logger

logger = get_logger(__name__)

_UNLOGGED_PATHS = {"/health"}  # polled every few seconds by the host


async def log_request(request: Request, call_next):
    """Assign `request.state.request_id` before the route runs, so a route
    that enqueues a job can pass it on (SyncJobLog.request_id), then log one
    line per request and echo the id back as `X-Request-ID`."""
    request_id = uuid.uuid4()
    request.state.request_id = request_id
    structlog.contextvars.bind_contextvars(request_id=str(request_id))
    started_at = time.monotonic()
    try:
        response = await call_next(request)
        if request.url.path not in _UNLOGGED_PATHS:
            logger.info(
                "request",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                latency_ms=round((time.monotonic() - started_at) * 1000, 1),
            )
        response.headers["X-Request-ID"] = str(request_id)
        return response
    finally:
        structlog.contextvars.unbind_contextvars("request_id")


async def log_error(
    exception_type: str, message: str, *, context: str, request_id=None, user_id=None
) -> None:
    """Persist one ErrorLog row. A failure here is logged and swallowed —
    it must never turn into a second failure on top of the one being handled."""
    try:
        async with async_session_factory() as db:
            db.add(
                ErrorLog(
                    exception_type=exception_type,
                    message=message,
                    context=context,
                    request_id=request_id,
                    user_id=user_id,
                )
            )
            await db.commit()
    except Exception:
        logger.exception("error_log_write_failed")
