"""Orchestration for one user's sync: valid token -> fetch -> upsert -> SyncJobLog."""

import time
from datetime import timedelta

import structlog

from core.clock import utcnow
from core.config import settings
from core.crypto import decrypt_token, encrypt_token
from core.db import async_session_factory
from core.exceptions import MissingCredentialError, UpstreamAuthError
from core.logging import get_logger
from core.queue import get_current_job
from core.redis_client import get_redis_conn
from services.whoop import client, crud
from services.whoop.config import SYNC_OVERLAP_DAYS
from services.whoop.models import SyncJobLog, User

_ATTEMPT_COUNTER_TTL_SECONDS = 86400  # outlives any retry sequence

logger = get_logger(__name__)


async def _valid_token(user: User, db) -> str:
    """A usable access token, refreshed (and re-stored, since WHOOP rotates the
    refresh token) if expired.

    Raises:
        MissingCredentialError: If the user never connected WHOOP.
        UpstreamAuthError: If WHOOP rejects the refresh.
    """
    if user.encrypted_access_token is None or user.encrypted_refresh_token is None:
        raise MissingCredentialError(str(user.id))

    if user.token_expires_at is not None and user.token_expires_at > utcnow():
        return decrypt_token(user.encrypted_access_token, settings.token_encryption_key)

    refresh_token = decrypt_token(user.encrypted_refresh_token, settings.token_encryption_key)
    tokens = await client.refresh_access_token(refresh_token)
    await crud.update_tokens(
        db,
        user.id,
        encrypt_token(tokens["access_token"], settings.token_encryption_key),
        encrypt_token(tokens["refresh_token"], settings.token_encryption_key),
        expires_in=tokens["expires_in"],
    )
    return tokens["access_token"]


async def sync_one_user(
    user_id: str, trigger_source: str = "manual", request_id: str | None = None
) -> dict:
    """Sync one user. Opens its own session, so it runs the same from a worker,
    a route or a test; writes one SyncJobLog row per attempt (RQ retries
    re-run the whole function).

    Args:
        user_id: The user to sync.
        trigger_source: "login" | "cron" | "manual".
        request_id: X-Request-ID of the request that enqueued this, if any.
    """
    job = get_current_job()  # None outside a worker process
    structlog.contextvars.bind_contextvars(user_id=user_id, job_id=job.id if job else None)
    logger.info("sync_started")
    started_at = time.monotonic()
    try:
        async with async_session_factory() as db:
            try:
                user = await crud.get_user(db, user_id)
                token = await _valid_token(user, db)
                since = await _fetch_since(db, user_id)
                data = await client.fetch_all(token, since)

                for c in data.cycles:
                    await crud.upsert_cycle(db, user_id, c)
                for r in data.recoveries:
                    await crud.upsert_recovery(db, user_id, r)
                for s in data.sleep:
                    await crud.upsert_sleep(db, user_id, s)
                for w in data.workouts:
                    await crud.upsert_workout(db, user_id, w)
                if data.body is not None:
                    await crud.upsert_body_measurement(db, user_id, data.body)
                await db.commit()  # once for the whole batch

                counts = {
                    "recoveries": len(data.recoveries),
                    "sleep": len(data.sleep),
                    "workouts": len(data.workouts),
                    "cycles": len(data.cycles),
                }
                logger.info("sync_complete", **counts)
                await _write_sync_job_log(
                    db,
                    user_id=user_id,
                    job=job,
                    trigger_source=trigger_source,
                    request_id=request_id,
                    duration_ms=(time.monotonic() - started_at) * 1000,
                    counts=counts,
                    error_message=None,
                )
                return {"user_id": user_id, **counts}
            except Exception as exc:
                logger.exception("sync_failed")
                if isinstance(exc, UpstreamAuthError) and exc.credential_revoked:
                    await db.rollback()
                    await crud.mark_disconnected(db, user_id)
                    logger.warning("user_disconnected_after_revoked_grant")
                # A failed flush leaves the session unusable until rolled back,
                # which would also lose the SyncJobLog row below.
                await db.rollback()
                await _write_sync_job_log(
                    db,
                    user_id=user_id,
                    job=job,
                    trigger_source=trigger_source,
                    request_id=request_id,
                    duration_ms=(time.monotonic() - started_at) * 1000,
                    counts={"recoveries": 0, "sleep": 0, "workouts": 0, "cycles": 0},
                    error_message=str(exc),
                )
                raise
    finally:
        structlog.contextvars.clear_contextvars()


async def _fetch_since(db, user_id: str):
    """Where this sync starts: full history on the first sync, or when stored
    records predate full-detail storage; otherwise the last successful sync
    minus an overlap (WHOOP scores recent records after the fact)."""
    if await crud.needs_full_sync(db, user_id):
        return None
    last_sync = await crud.last_successful_sync_at(db, user_id)
    return last_sync - timedelta(days=SYNC_OVERLAP_DAYS) if last_sync else None


async def _attempt_number(job) -> int:
    """Which attempt this is for `job`, counted in Redis — RQ's own retry count
    isn't reliably visible to the running job.
    """
    if job is None:
        return 1
    key = f"whoop:sync-attempt:{job.id}"
    async with get_redis_conn() as conn:
        count = await conn.incr(key)
        await conn.expire(key, _ATTEMPT_COUNTER_TTL_SECONDS)
    return int(count)


async def _write_sync_job_log(
    db,
    *,
    user_id: str,
    job,
    trigger_source: str,
    request_id: str | None,
    duration_ms: float,
    counts: dict,
    error_message: str | None,
) -> None:
    """Write one SyncJobLog row; failures are logged and swallowed so they never
    mask the sync's real outcome.
    """
    try:
        db.add(
            SyncJobLog(
                user_id=user_id,
                request_id=request_id,
                job_id=job.id if job else None,
                attempt_number=await _attempt_number(job),
                trigger_source=trigger_source,
                status="failed" if error_message else "success",
                retries_left=job.retries_left if job else None,
                recoveries_synced=counts["recoveries"],
                sleep_synced=counts["sleep"],
                workouts_synced=counts["workouts"],
                cycles_synced=counts["cycles"],
                duration_ms=duration_ms,
                error_message=error_message,
            )
        )
        await db.commit()
    except Exception:
        logger.exception("sync_job_log_write_failed")
