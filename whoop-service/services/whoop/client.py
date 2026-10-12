"""The only module that calls WHOOP's HTTP API: OAuth exchange/refresh and the
paginated, retried, concurrency-bounded data fetch.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime

import httpx
import structlog

from core.exceptions import UpstreamAuthError
from services.whoop import circuit_breaker
from services.whoop.config import (
    WHOOP_API_BASE_URL,
    WHOOP_FETCH_MAX_ATTEMPTS,
    WHOOP_MAX_PAGES,
    WHOOP_PAGE_SIZE,
    WHOOP_RETRYABLE_STATUSES,
    WHOOP_TOKEN_URL,
    whoop_settings,
)
from services.whoop.whoop_types import (
    BodyMeasurement,
    CycleRecord,
    Profile,
    RecoveryRecord,
    SleepRecord,
    WorkoutRecord,
)

logger = structlog.get_logger(__name__)


async def exchange_code_for_tokens(code: str, code_verifier: str) -> dict:
    """Exchange an OAuth code (plus its PKCE verifier) for a token pair.

    Raises:
        UpstreamAuthError: If WHOOP rejects the exchange.
    """
    async with httpx.AsyncClient(timeout=10.0) as http:
        r = await http.post(
            WHOOP_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": whoop_settings.whoop_client_id,
                "client_secret": whoop_settings.whoop_client_secret,
                "redirect_uri": whoop_settings.whoop_redirect_uri,
                "code_verifier": code_verifier,
            },
        )
        if r.is_error:
            raise UpstreamAuthError(f"code exchange failed with {r.status_code}", r.status_code)
    return r.json()


async def refresh_access_token(refresh_token: str) -> dict:
    """Trade a refresh token for a new pair — WHOOP rotates the refresh token,
    so callers must store both.

    Raises:
        UpstreamAuthError: If WHOOP rejects the refresh.
    """
    async with httpx.AsyncClient(timeout=10.0) as http:
        r = await http.post(
            WHOOP_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": whoop_settings.whoop_client_id,
                "client_secret": whoop_settings.whoop_client_secret,
            },
        )
        if r.is_error:
            raise UpstreamAuthError(f"refresh grant failed with {r.status_code}", r.status_code)
    return r.json()


async def fetch_profile(access_token: str) -> Profile:
    """The WHOOP account behind a token — its id identifies a returning user.

    Raises:
        UpstreamAuthError: If WHOOP rejects the profile request.
    """
    async with httpx.AsyncClient(timeout=10.0) as http:
        r = await http.get(
            f"{WHOOP_API_BASE_URL}/v2/user/profile/basic",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if r.is_error:
            raise UpstreamAuthError(f"profile request failed with {r.status_code}", r.status_code)
    return Profile.model_validate(r.json())


async def _get_page(
    client: httpx.AsyncClient, sem: asyncio.Semaphore, path: str, token: str, params: dict
) -> dict:
    """One bounded, unretried GET for one page of a WHOOP collection."""
    async with sem:
        r = await client.get(
            f"{WHOOP_API_BASE_URL}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )
        r.raise_for_status()
        return r.json()


async def _get_page_with_retry(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    path: str,
    token: str,
    params: dict,
    max_attempts: int = WHOOP_FETCH_MAX_ATTEMPTS,
) -> dict:
    """Retry `_get_page` with exponential backoff on transient failures only.
    Non-transient failures (401/403) propagate immediately."""
    for attempt in range(1, max_attempts + 1):
        try:
            return await _get_page(client, sem, path, token, params)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in WHOOP_RETRYABLE_STATUSES or attempt == max_attempts:
                raise
            delay = 2**attempt
            logger.warning(
                "whoop_request_retrying",
                path=path,
                status=exc.response.status_code,
                attempt=attempt,
                delay=delay,
            )
            await asyncio.sleep(delay)
        except httpx.TimeoutException:
            if attempt == max_attempts:
                raise
            await asyncio.sleep(2**attempt)
    raise RuntimeError("unreachable")  # loop above always returns or raises


async def _get_all(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    path: str,
    token: str,
    since: datetime | None,
) -> list[dict]:
    """Every record of one collection, following `next_token` up to WHOOP_MAX_PAGES."""
    params: dict = {"limit": WHOOP_PAGE_SIZE}
    if since is not None:
        params["start"] = since.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    records: list[dict] = []
    for _ in range(WHOOP_MAX_PAGES):
        page = await _get_page_with_retry(client, sem, path, token, params)
        records.extend(page.get("records", []))
        next_token = page.get("next_token")
        if not next_token:
            break
        params = {**params, "nextToken": next_token}
    return records


@dataclass(frozen=True)
class WhoopData:
    recoveries: list[RecoveryRecord]
    sleep: list[SleepRecord]
    workouts: list[WorkoutRecord]
    cycles: list[CycleRecord]
    body: BodyMeasurement | None


def _scope_not_granted(exc: httpx.HTTPStatusError) -> bool:
    # Tokens issued before a scope was added can't read that endpoint until
    # the user reconnects; that's a gap in the data, not a failed sync.
    return exc.response.status_code in (401, 403)


async def _get_optional_all(
    client: httpx.AsyncClient, sem: asyncio.Semaphore, path: str, token: str, since: datetime | None
) -> list[dict]:
    try:
        return await _get_all(client, sem, path, token, since)
    except httpx.HTTPStatusError as exc:
        if not _scope_not_granted(exc):
            raise
        logger.warning("whoop_scope_not_granted", path=path)
        return []


async def _get_body(client: httpx.AsyncClient, sem: asyncio.Semaphore, token: str) -> dict | None:
    try:
        return await _get_page_with_retry(client, sem, "/v2/user/measurement/body", token, {})
    except httpx.HTTPStatusError as exc:
        if not _scope_not_granted(exc):
            raise
        logger.warning("whoop_scope_not_granted", path="/v2/user/measurement/body")
        return None


async def fetch_all(token: str, since: datetime | None = None) -> WhoopData:
    """Fetch every collection concurrently — recovery, sleep, workouts, cycles —
    plus the body measurement, parsed into typed records. `since` (naive UTC)
    narrows collections to recent records; None fetches history. Cycles and body
    measurement are skipped when the token predates their scopes.

    Raises:
        WhoopDegradedError: If the circuit breaker is open (checked first).
        pydantic.ValidationError: If WHOOP's response shape changed.
    """
    await circuit_breaker.raise_if_open()
    sem = asyncio.Semaphore(whoop_settings.whoop_fetch_concurrency)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            raw_recoveries, raw_sleep, raw_workouts, raw_cycles, raw_body = await asyncio.gather(
                _get_all(client, sem, "/v2/recovery", token, since),
                _get_all(client, sem, "/v2/activity/sleep", token, since),
                _get_all(client, sem, "/v2/activity/workout", token, since),
                _get_optional_all(client, sem, "/v2/cycle", token, since),
                _get_body(client, sem, token),
            )
    except (httpx.HTTPStatusError, httpx.TimeoutException):
        # Only fetch failures trip the breaker, never a parsing bug below.
        await circuit_breaker.record_failure()
        raise
    await circuit_breaker.record_success()
    return WhoopData(
        recoveries=[RecoveryRecord.model_validate(r) for r in raw_recoveries],
        sleep=[SleepRecord.model_validate(r) for r in raw_sleep],
        workouts=[WorkoutRecord.model_validate(r) for r in raw_workouts],
        cycles=[CycleRecord.model_validate(r) for r in raw_cycles],
        body=BodyMeasurement.model_validate(raw_body) if raw_body else None,
    )
