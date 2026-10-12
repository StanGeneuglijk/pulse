"""Insight-specific domain exceptions."""

from core.exceptions import DomainError


class InsufficientDataError(DomainError):
    """No WHOOP data in the window — nothing to summarize, nothing billed."""

    def __init__(self, user_id: str, window_days: int) -> None:
        self.user_id = user_id
        self.window_days = window_days
        super().__init__(
            f"user {user_id} has no WHOOP data in the last {window_days} days"
        )


class GenerationLockedError(DomainError):
    """A generation is already running for this user."""

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        super().__init__(f"a generation is already in progress for user {user_id}")


class NoInsightFoundError(DomainError):
    """No insight generated yet for this user and period."""

    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        super().__init__(f"no insight has been generated yet for user {user_id}")


class LLMProviderError(DomainError):
    """The configured LLM provider failed or returned something unusable."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"LLM provider call failed: {reason}")


class SpendLimitExceededError(DomainError):
    """Estimated spend reached the per-user or platform cap."""

    def __init__(self, spent_usd: float, limit_usd: float) -> None:
        self.spent_usd = spent_usd
        self.limit_usd = limit_usd
        super().__init__(
            f"estimated spend ${spent_usd:.4f} has reached the ${limit_usd:.2f} cap"
        )
