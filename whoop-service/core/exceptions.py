"""Domain exceptions any product on this core/ can raise. Product-specific ones
subclass DomainError in their own package; only api/main.py maps them to HTTP.
"""


class DomainError(Exception):
    """Base type for every exception below. Never raised directly."""


class UserNotFoundError(DomainError):
    """No user exists for the given id."""

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        super().__init__(f"no such user: {user_id}")


class MissingCredentialError(DomainError):
    """A sync was attempted for a user with no stored credential."""

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        super().__init__(f"user {user_id} has no stored credential")


class InvalidOAuthStateError(DomainError):
    """A callback's `state` doesn't match a pending login."""

    def __init__(self) -> None:
        super().__init__("invalid or missing OAuth state")


class UpstreamAuthError(DomainError):
    """The upstream OAuth provider rejected a code exchange or refresh."""

    def __init__(self, reason: str, status_code: int | None = None) -> None:
        self.reason = reason
        self.status_code = status_code
        super().__init__(f"upstream rejected the token request: {reason}")

    @property
    def credential_revoked(self) -> bool:
        """400/401 means the grant itself is dead (revoked, or a refresh token
        already rotated away) — retrying can't fix it; reconnecting can."""
        return self.status_code in (400, 401)


class BatchAlreadyInFlightError(DomainError):
    """`/sync/batch` was called again before the debounce window elapsed."""

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__("a sync batch was already triggered recently")


class BatchTooLargeError(DomainError):
    """`/sync/batch` would enqueue more than SYNC_BATCH_MAX_USERS jobs."""

    def __init__(self, connected_count: int, max_allowed: int) -> None:
        self.connected_count = connected_count
        self.max_allowed = max_allowed
        super().__init__(
            f"{connected_count} connected users exceeds the {max_allowed}-user batch cap"
        )


class DependencyUnavailableError(DomainError):
    """A required dependency (database, broker) didn't respond."""

    def __init__(self, dependency: str) -> None:
        self.dependency = dependency
        super().__init__(f"{dependency} is unreachable")


class InvalidApiKeyError(DomainError):
    """A protected route was called with a missing or incorrect API key."""

    def __init__(self) -> None:
        super().__init__("missing or invalid API key")


class InvalidExchangeCodeError(DomainError):
    """`/auth/exchange` got a code that's unknown, used or expired."""

    def __init__(self) -> None:
        super().__init__("invalid or expired exchange code")
