"""HTTP routes for the WHOOP product: validate, delegate to one layer, shape the response."""

import base64
import hashlib
import secrets
import uuid
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlencode

import structlog
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import require_api_key
from core.config import settings
from core.crypto import encrypt_token
from core.db import get_db
from core.exceptions import (
    BatchAlreadyInFlightError,
    BatchTooLargeError,
    InvalidExchangeCodeError,
    InvalidOAuthStateError,
)
from core.locks import acquire_lock
from core.oauth_state import OAuthStateStore
from core.one_time_code import OneTimeCodeStore
from core.queue import Queue, Retry
from services.whoop import client, crud
from services.whoop.activity_log import log_activity
from services.whoop.auth import require_user_access
from services.whoop.config import (
    BATCH_LOCK_KEY,
    BATCH_LOCK_TTL_SECONDS,
    EXCHANGE_CODE_KEY_PREFIX,
    EXCHANGE_CODE_TTL_SECONDS,
    OAUTH_STATE_KEY_PREFIX,
    OAUTH_STATE_TTL_SECONDS,
    SYNC_BATCH_MAX_USERS,
    SYNC_JOB_RETRY_MAX,
    SYNC_JOB_TIMEOUT_SECONDS,
    USER_SYNC_LOCK_KEY_PREFIX,
    USER_SYNC_LOCK_TTL_SECONDS,
    WHOOP_AUTH_URL,
    WHOOP_OAUTH_SCOPE,
    sync_queue,
    whoop_settings,
)
from services.whoop.models import SyncJobLog, UserActivityLog
from services.whoop.schemas import (
    ActivityLogResponse,
    AuthCallbackResponse,
    CycleResponse,
    ExchangeCodeRequest,
    ProfileResponse,
    RecordResponse,
    RecoveryResponse,
    SleepResponse,
    SyncBatchResponse,
    SyncLogResponse,
    SyncTriggerResponse,
    WorkoutResponse,
)

router = APIRouter(tags=["whoop"])

_oauth_states = OAuthStateStore(OAUTH_STATE_KEY_PREFIX, OAUTH_STATE_TTL_SECONDS)
_exchange_codes = OneTimeCodeStore(EXCHANGE_CODE_KEY_PREFIX, EXCHANGE_CODE_TTL_SECONDS)


def _list_or_304(
    records: list, model: type[RecordResponse], request: Request, response: Response
) -> list[dict] | Response:
    """Serialize records, or return a bare 304 when the client's ETag (a hash of each
    record's id + content_hash) still matches.
    """
    fingerprint = ",".join(
        f"{r.id}:{r.content_hash}" for r in sorted(records, key=lambda r: str(r.id))
    )
    etag = f'"{hashlib.sha256(fingerprint.encode()).hexdigest()}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    response.headers["ETag"] = etag
    return [
        model.model_validate(r).model_dump(mode="json", by_alias=True) for r in records
    ]


@router.get("/auth/login")
async def login() -> RedirectResponse:
    """Redirect to WHOOP's login with a CSRF `state` and a PKCE challenge, both
    stored in Redis so any API instance can complete the callback.
    """
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)  # 43-128 chars required; this is ~86
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    await _oauth_states.create(state, code_verifier)
    params = {
        "client_id": whoop_settings.whoop_client_id,
        "redirect_uri": whoop_settings.whoop_redirect_uri,
        "response_type": "code",
        "scope": WHOOP_OAUTH_SCOPE,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return RedirectResponse(f"{WHOOP_AUTH_URL}?{urlencode(params)}")


@router.get("/auth/callback")
async def callback(
    code: str, state: str, request: Request, db: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    """Finish OAuth: check `state`, exchange the code (with the PKCE verifier),
    identify the WHOOP account, store encrypted tokens on that account's user
    (created on first connect, updated on reconnect), enqueue a sync, and
    redirect to the frontend with a one-time code — never the `read_token`
    itself in a URL.

    Raises:
        InvalidOAuthStateError: If `state` doesn't match a pending login.
        UpstreamAuthError: If WHOOP rejects the code exchange.
    """
    code_verifier = await _oauth_states.consume(state)
    if code_verifier is None:
        raise InvalidOAuthStateError()

    tokens = await client.exchange_code_for_tokens(code, code_verifier)
    profile = await client.fetch_profile(tokens["access_token"])

    user = await crud.connect_user(
        db,
        profile=profile,
        encrypted_access_token=encrypt_token(tokens["access_token"], settings.token_encryption_key),
        encrypted_refresh_token=encrypt_token(
            tokens["refresh_token"], settings.token_encryption_key
        ),
        expires_in=tokens["expires_in"],
    )

    sync_queue.enqueue(
        "services.whoop.sync.sync_one_user",
        str(user.id),
        "login",
        str(request.state.request_id),
        job_timeout=SYNC_JOB_TIMEOUT_SECONDS,
        retry=Retry(max=SYNC_JOB_RETRY_MAX),
    )

    exchange_code = await _exchange_codes.create(
        {"user_id": str(user.id), "read_token": user.read_token}
    )
    return RedirectResponse(f"{settings.frontend_url}/connected?code={exchange_code}")


@router.post("/auth/exchange", response_model=AuthCallbackResponse)
async def exchange(body: ExchangeCodeRequest) -> AuthCallbackResponse:
    """Redeem a one-time code (single use, 60s) for `userId` + `readToken`.

    Raises:
        InvalidExchangeCodeError: If the code is unknown, used or expired.
    """
    payload = await _exchange_codes.consume(body.code)
    if payload is None:
        raise InvalidExchangeCodeError()
    return AuthCallbackResponse(
        connected=True, user_id=uuid.UUID(payload["user_id"]), read_token=payload["read_token"]
    )


@router.post(
    "/sync/batch",
    status_code=202,
    response_model=SyncBatchResponse,
    dependencies=[Depends(require_api_key)],
)
async def sync_batch(request: Request, db: AsyncSession = Depends(get_db)) -> SyncBatchResponse:
    """Enqueue one sync per connected user in a single pipelined Redis call.

    Raises:
        BatchAlreadyInFlightError: If a batch ran within the debounce window.
        BatchTooLargeError: If connected users exceed SYNC_BATCH_MAX_USERS —
            refused rather than silently truncated.
    """
    if not await acquire_lock(BATCH_LOCK_KEY, BATCH_LOCK_TTL_SECONDS):
        raise BatchAlreadyInFlightError(BATCH_LOCK_TTL_SECONDS)

    user_ids = await crud.list_connected_user_ids(db)
    if len(user_ids) > SYNC_BATCH_MAX_USERS:
        raise BatchTooLargeError(len(user_ids), SYNC_BATCH_MAX_USERS)

    retry = Retry(max=SYNC_JOB_RETRY_MAX)
    request_id = str(request.state.request_id)
    job_data = [
        Queue.prepare_data(
            "services.whoop.sync.sync_one_user",
            args=(str(user_id), "cron", request_id),
            timeout=SYNC_JOB_TIMEOUT_SECONDS,
            retry=retry,
        )
        for user_id in user_ids
    ]
    if job_data:
        sync_queue.enqueue_many(job_data)

    return SyncBatchResponse(queued=len(user_ids))


RecordLister = Callable[[AsyncSession, str], Awaitable[list[Any]]]


async def _records(
    kind: str,
    list_records: RecordLister,
    model: type[RecordResponse],
    user_id: uuid.UUID,
    request: Request,
    response: Response,
    db: AsyncSession,
) -> list[dict] | Response:
    structlog.contextvars.bind_contextvars(user_id=str(user_id))
    try:
        records = await list_records(db, str(user_id))
        await log_activity(db, user_id, kind)
        return _list_or_304(records, model, request, response)
    finally:
        structlog.contextvars.clear_contextvars()


@router.get(
    "/users/{user_id}/recovery", response_model=None, dependencies=[Depends(require_user_access)]
)
async def get_recovery(
    user_id: uuid.UUID, request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> list[dict] | Response:
    """This user's recoveries (recovery %, HRV, resting HR, SpO2, skin temp), newest first."""
    return await _records(
        "recovery", crud.list_recovery, RecoveryResponse, user_id, request, response, db
    )


@router.get(
    "/users/{user_id}/sleep", response_model=None, dependencies=[Depends(require_user_access)]
)
async def get_sleep(
    user_id: uuid.UUID, request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> list[dict] | Response:
    """This user's sleeps (performance, stages, need, efficiency), newest first."""
    return await _records("sleep", crud.list_sleep, SleepResponse, user_id, request, response, db)


@router.get(
    "/users/{user_id}/workout", response_model=None, dependencies=[Depends(require_user_access)]
)
async def get_workout(
    user_id: uuid.UUID, request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> list[dict] | Response:
    """This user's workouts (strain, sport, heart rate, zones), newest first."""
    return await _records(
        "workout", crud.list_workout, WorkoutResponse, user_id, request, response, db
    )


@router.get(
    "/users/{user_id}/cycles", response_model=None, dependencies=[Depends(require_user_access)]
)
async def get_cycles(
    user_id: uuid.UUID, request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> list[dict] | Response:
    """This user's cycles (day strain, energy, heart rate), newest first."""
    return await _records("cycles", crud.list_cycles, CycleResponse, user_id, request, response, db)


@router.get(
    "/users/{user_id}/profile",
    response_model=ProfileResponse,
    dependencies=[Depends(require_user_access)],
)
async def get_profile(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> ProfileResponse:
    """Name and latest body measurement."""
    user = await crud.get_user(db, str(user_id))
    body = await crud.get_body_measurement(db, str(user_id))
    return ProfileResponse(
        first_name=user.first_name,
        last_name=user.last_name,
        height_meter=body.height_meter if body else None,
        weight_kilogram=body.weight_kilogram if body else None,
        max_heart_rate=body.max_heart_rate if body else None,
    )


@router.post(
    "/users/{user_id}/sync",
    status_code=202,
    response_model=SyncTriggerResponse,
    dependencies=[Depends(require_user_access)],
)
async def sync_user(
    user_id: uuid.UUID, request: Request, db: AsyncSession = Depends(get_db)
) -> SyncTriggerResponse:
    """Queue a sync for this user (the dashboard's refresh), debounced per user:
    a repeat within the lock window returns `{"queued": false}`.
    """
    structlog.contextvars.bind_contextvars(user_id=str(user_id))
    try:
        if not await acquire_lock(
            f"{USER_SYNC_LOCK_KEY_PREFIX}{user_id}", USER_SYNC_LOCK_TTL_SECONDS
        ):
            return SyncTriggerResponse(queued=False)
        sync_queue.enqueue(
            "services.whoop.sync.sync_one_user",
            str(user_id),
            "manual",
            str(request.state.request_id),
            job_timeout=SYNC_JOB_TIMEOUT_SECONDS,
            retry=Retry(max=SYNC_JOB_RETRY_MAX),
        )
        return SyncTriggerResponse(queued=True)
    finally:
        structlog.contextvars.clear_contextvars()


@router.get(
    "/users/{user_id}/activity",
    response_model=list[ActivityLogResponse],
    dependencies=[Depends(require_user_access)],
)
async def get_activity(
    user_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[UserActivityLog]:
    """This user's recent API activity."""
    structlog.contextvars.bind_contextvars(user_id=str(user_id))
    try:
        return await crud.list_activity(db, str(user_id))
    finally:
        structlog.contextvars.clear_contextvars()


@router.get(
    "/users/{user_id}/syncs",
    response_model=list[SyncLogResponse],
    dependencies=[Depends(require_user_access)],
)
async def get_syncs(user_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> list[SyncJobLog]:
    """This user's recent sync attempts — what the dashboard's "last sync" reads."""
    structlog.contextvars.bind_contextvars(user_id=str(user_id))
    try:
        return await crud.list_syncs(db, str(user_id))
    finally:
        structlog.contextvars.clear_contextvars()
