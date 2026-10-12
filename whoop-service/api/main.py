"""API entrypoint: aggregates routers and maps domain exceptions to HTTP
responses. No business logic — see services/whoop/router.py.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.config import settings
from core.exceptions import (
    BatchAlreadyInFlightError,
    BatchTooLargeError,
    DependencyUnavailableError,
    DomainError,
    InvalidApiKeyError,
    InvalidExchangeCodeError,
    InvalidOAuthStateError,
    MissingCredentialError,
    UpstreamAuthError,
    UserNotFoundError,
)
from core.health import check_health
from core.logging import configure_logging, get_logger
from core.request_logging import log_error, log_request
from services.whoop.router import router as whoop_router

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("api_started")
    yield


app = FastAPI(title="whoop-service", lifespan=lifespan)
app.include_router(whoop_router)
app.middleware("http")(log_request)


@app.get("/health")
async def health() -> dict:
    return await check_health()


@app.get("/version")
async def version() -> dict:
    """Which commit is live, so a deploy can be checked against the merged one."""
    return {"commit": settings.render_git_commit}


# Domain exception -> (status code, whether it's persisted to ErrorLog).
# Client mistakes that happen routinely (bad key, expired code, debounce)
# are logged to stdout only.
_ERROR_STATUS: dict[type[DomainError], tuple[int, bool]] = {
    UserNotFoundError: (404, True),
    MissingCredentialError: (409, True),
    InvalidOAuthStateError: (400, True),
    UpstreamAuthError: (502, True),
    BatchTooLargeError: (400, True),
    InvalidApiKeyError: (401, False),
    InvalidExchangeCodeError: (401, False),
    BatchAlreadyInFlightError: (429, False),
    DependencyUnavailableError: (503, False),
}


@app.exception_handler(DomainError)
async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    status, persist = _ERROR_STATUS.get(type(exc), (500, True))
    name = type(exc).__name__
    log = logger.error if status >= 500 or persist else logger.warning
    log("domain_error", error=name, path=request.url.path, **vars(exc))
    if persist:
        await log_error(
            name,
            str(exc),
            context=request.url.path,
            request_id=request.state.request_id,
            user_id=getattr(exc, "user_id", None),
        )

    headers = {}
    if isinstance(exc, InvalidApiKeyError):
        headers["WWW-Authenticate"] = "Bearer"
    if isinstance(exc, BatchAlreadyInFlightError):
        headers["Retry-After"] = str(exc.retry_after_seconds)
    # Upstream failures stay generic — the real reason is in the logs.
    detail = "WHOOP authentication failed" if isinstance(exc, UpstreamAuthError) else str(exc)
    content: dict = {"detail": detail}
    if isinstance(exc, DependencyUnavailableError):
        content["status"] = "unhealthy"
    return JSONResponse(status_code=status, content=content, headers=headers)
