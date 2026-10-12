"""Product-agnostic settings: database, cache, caller auth. This product's own
LLM settings live in its services/<product>/config.py.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    database_url_direct: str | None = None  # unpooled — Alembic only, see alembic/env.py
    redis_url: str
    api_key: str  # caller auth — see core/auth.py

    render_git_commit: str = "local"  # set by Render on every deploy — see /version

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


# /health reuses a successful Redis ping for this long. Render polls /health every
# ~10 s per service, and Upstash's free plan allows 500K commands a month: a ping
# on every poll alone used ~100K a day. See specs/whoop-service/plan.md, Hosting.
REDIS_HEALTH_TTL_SECONDS = 300


settings = Settings()  # type: ignore[call-arg]  # values come from the environment
