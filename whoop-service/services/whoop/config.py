"""WHOOP-specific settings and fixed policy: URLs, OAuth credentials, retry,
pagination, job, lock and circuit-breaker constants, and the sync queue."""

from pydantic_settings import BaseSettings, SettingsConfigDict

from core.queue import Queue, redis_conn


class WhoopSettings(BaseSettings):
    whoop_client_id: str
    whoop_client_secret: str
    whoop_redirect_uri: str
    whoop_fetch_concurrency: int = 3

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


whoop_settings = WhoopSettings()  # type: ignore[call-arg]  # values come from the environment


# WHOOP's own fixed endpoints and scope
WHOOP_AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
WHOOP_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"  # noqa: S105 — a URL, not a secret
WHOOP_API_BASE_URL = "https://api.prod.whoop.com/developer"
WHOOP_OAUTH_SCOPE = (
    "read:profile read:body_measurement read:cycles read:recovery read:sleep read:workout offline"
)

# Retry policy against WHOOP
WHOOP_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
WHOOP_FETCH_MAX_ATTEMPTS = 3

# Collection pagination: 25 is WHOOP's max page size; 40 pages bounds a
# first sync at ~1000 records (~2.5 years of daily data) per collection.
WHOOP_PAGE_SIZE = 25
WHOOP_MAX_PAGES = 40
# Later syncs re-fetch from the last successful sync minus this overlap —
# WHOOP scores a recovery/sleep after the fact, so recent records change.
SYNC_OVERLAP_DAYS = 3

# Sync job policy
SYNC_JOB_TIMEOUT_SECONDS = 120
# Retries are immediate: delayed retries need RQ's scheduler, which polls Redis every
# second and exhausts Upstash's free command quota. Backoff against WHOOP lives in the client.
SYNC_JOB_RETRY_MAX = 3

# Batch-trigger debounce
BATCH_LOCK_KEY = "whoop:sync-batch:lock"
BATCH_LOCK_TTL_SECONDS = 300

# Per-user manual-sync debounce — a user spamming "refresh" queues one job
USER_SYNC_LOCK_KEY_PREFIX = "whoop:sync-user:lock:"
USER_SYNC_LOCK_TTL_SECONDS = 60

# Batch fan-out safety cap: crossing it is an anomaly to look at (a leaked
# key, an operator error), never something to silently truncate.
SYNC_BATCH_MAX_USERS = 10_000

# OAuth CSRF state + PKCE verifier, per in-flight login
OAUTH_STATE_KEY_PREFIX = "oauth:state:"
OAUTH_STATE_TTL_SECONDS = 600

# One-time code that hands a new read_token to the frontend (redirect + one POST)
EXCHANGE_CODE_KEY_PREFIX = "exchange:code:"
EXCHANGE_CODE_TTL_SECONDS = 60

# Circuit breaker: consecutive fetch failures across all jobs before failing fast
WHOOP_CIRCUIT_FAILURE_KEY = "whoop:circuit:consecutive_failures"
WHOOP_CIRCUIT_THRESHOLD = 5
WHOOP_CIRCUIT_TTL_SECONDS = 120

# This product's named queue (core/queue.py only holds the connection).
sync_queue = Queue("whoop-sync", connection=redis_conn)
