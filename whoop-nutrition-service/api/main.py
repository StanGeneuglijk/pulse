"""API entrypoint: aggregates routers and maps domain exceptions to HTTP
responses. No business logic — see services/nutrition/router.py.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.config import settings
from core.exceptions import DependencyUnavailableError, DomainError, InvalidApiKeyError
from core.health import check_health
from core.logging import configure_logging, get_logger
from services.nutrition.exceptions import (
    AudioTooLargeError,
    ConversationLockedError,
    ConversationNotFoundError,
    LLMProviderError,
    NoPendingMealError,
    SpendLimitExceededError,
    TranscriptionFailedError,
    TranscriptionNotConfiguredError,
)
from services.nutrition.router import router as nutrition_router

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("api_started")
    yield


app = FastAPI(title="whoop-nutrition-service", lifespan=lifespan)
app.include_router(nutrition_router)


@app.get("/health")
async def health() -> dict:
    return await check_health()


@app.get("/version")
async def version() -> dict:
    """Which commit is live, so a deploy can be checked against the merged one."""
    return {"commit": settings.render_git_commit}


_ERROR_STATUS: dict[type[DomainError], int] = {
    NoPendingMealError: 409,
    ConversationLockedError: 409,
    ConversationNotFoundError: 404,
    SpendLimitExceededError: 402,
    AudioTooLargeError: 413,
    TranscriptionFailedError: 422,
    LLMProviderError: 502,
    TranscriptionNotConfiguredError: 503,
    DependencyUnavailableError: 503,
    InvalidApiKeyError: 401,
}


@app.exception_handler(DomainError)
async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    status = _ERROR_STATUS.get(type(exc), 500)
    log = logger.error if status >= 500 or status == 402 else logger.warning
    log("domain_error", error=type(exc).__name__, path=request.url.path, **vars(exc))

    headers = {"WWW-Authenticate": "Bearer"} if isinstance(exc, InvalidApiKeyError) else {}
    # Provider failures stay generic — the real reason is in the logs.
    detail = "LLM provider call failed" if isinstance(exc, LLMProviderError) else str(exc)
    content: dict = {"detail": detail}
    if isinstance(exc, DependencyUnavailableError):
        content["status"] = "unhealthy"
    return JSONResponse(status_code=status, content=content, headers=headers)
