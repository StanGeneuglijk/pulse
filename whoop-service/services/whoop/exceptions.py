"""WHOOP-specific domain exceptions."""

from core.exceptions import DomainError


class WhoopDegradedError(DomainError):
    """The circuit breaker is open. Raised only inside a sync job, so it has no
    HTTP mapping — it fails the job like any other sync error.
    """

    def __init__(self, consecutive_failures: int) -> None:
        self.consecutive_failures = consecutive_failures
        super().__init__(f"WHOOP circuit open after {consecutive_failures} consecutive failures")
