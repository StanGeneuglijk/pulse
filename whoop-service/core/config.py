"""Product-agnostic settings: database, cache, caller auth, encryption key.
WHOOP's own settings live in services/whoop/config.py.
"""

from cryptography.fernet import Fernet
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    database_url_direct: str | None = None  # unpooled — Alembic only, see alembic/env.py
    redis_url: str
    token_encryption_key: str
    api_key: str  # caller auth — see core/auth.py
    frontend_url: str = "http://localhost:3000"  # where the OAuth callback redirects

    render_git_commit: str = "local"  # set by Render on every deploy — see /version

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("token_encryption_key")
    @classmethod
    def _validate_fernet_key(cls, value: str) -> str:
        """Reject a malformed key at startup rather than at first use."""
        try:
            Fernet(value.encode())
        except Exception as exc:
            raise ValueError(f"not a valid Fernet key: {exc}") from exc
        return value


# /health reuses a successful Redis ping for this long. Render polls /health every
# ~10 s per service, and Upstash's free plan allows 500K commands a month: a ping
# on every poll alone used ~100K a day. See specs/whoop-service/plan.md, Hosting.
REDIS_HEALTH_TTL_SECONDS = 300


settings = Settings()  # type: ignore[call-arg]  # values come from the environment
