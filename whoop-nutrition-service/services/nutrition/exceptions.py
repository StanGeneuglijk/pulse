"""Nutrition-specific domain exceptions."""

from core.exceptions import DomainError


class ConversationLockedError(DomainError):
    """A turn is already running for this conversation."""

    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id
        super().__init__(f"a turn is already in progress for conversation {conversation_id}")


class NoPendingMealError(DomainError):
    """Confirm/discard with nothing staged — a 409, never a silent no-op."""

    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id
        super().__init__(f"conversation {conversation_id} has no pending meal to resolve")


class ConversationNotFoundError(DomainError):
    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id
        super().__init__(f"no such conversation: {conversation_id}")


class SpendLimitExceededError(DomainError):
    """Estimated spend reached the per-user or platform cap."""

    def __init__(self, spent_usd: float, limit_usd: float) -> None:
        self.spent_usd = spent_usd
        self.limit_usd = limit_usd
        super().__init__(
            f"estimated spend ${spent_usd:.4f} has reached the ${limit_usd:.2f} cap"
        )


class LLMProviderError(DomainError):
    """The chat provider failed or returned something unusable."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"LLM provider call failed: {reason}")


class TranscriptionNotConfiguredError(DomainError):
    """Voice input was used without OPENAI_API_KEY set."""

    def __init__(self) -> None:
        super().__init__("voice input isn't configured on this deployment (OPENAI_API_KEY unset)")


class TranscriptionFailedError(DomainError):
    """Transcription failed, or the audio held no speech."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"transcription failed: {reason}")


class AudioTooLargeError(DomainError):
    """An uploaded voice message exceeds NUTRITION_MAX_AUDIO_BYTES."""

    def __init__(self, max_bytes: int) -> None:
        self.max_bytes = max_bytes
        super().__init__(f"audio upload exceeds {max_bytes // (1024 * 1024)} MB")
