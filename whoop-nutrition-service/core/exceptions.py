"""Domain exceptions any product on this core/ can raise. Product-specific ones
subclass DomainError in their own package; only api/main.py maps them to HTTP.
"""


class DomainError(Exception):
    """Base type for every exception below. Never raised directly."""


class DependencyUnavailableError(DomainError):
    """A required dependency (database, Redis) didn't respond."""

    def __init__(self, dependency: str) -> None:
        self.dependency = dependency
        super().__init__(f"{dependency} is unreachable")


class InvalidApiKeyError(DomainError):
    """A protected route was called with a missing or incorrect API key."""

    def __init__(self) -> None:
        super().__init__("missing or invalid API key")
