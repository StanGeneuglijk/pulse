"""Selects the concrete clients this deployment runs — Anthropic for chat,
OpenAI for transcription. A second provider is a new module plus one branch here.
"""

from functools import cache

from services.nutrition.config import nutrition_settings
from services.nutrition.exceptions import TranscriptionNotConfiguredError
from services.nutrition.llm import ChatLLMClient
from services.nutrition.providers.anthropic_client import AnthropicChatClient
from services.nutrition.providers.openai_whisper_client import OpenAIWhisperClient
from services.nutrition.transcription import TranscriptionClient


@cache
def get_llm_client() -> ChatLLMClient:
    """One client per process, so its HTTP connection pool is reused."""
    return AnthropicChatClient(
        api_key=nutrition_settings.anthropic_api_key,
        model=nutrition_settings.llm_model,
    )


def get_transcription_client() -> TranscriptionClient:
    """Resolved per request, so a deployment without OPENAI_API_KEY still
    starts — only the audio route fails.

    Raises:
        TranscriptionNotConfiguredError: If OPENAI_API_KEY is unset or empty.
    """
    if not nutrition_settings.openai_api_key:
        raise TranscriptionNotConfiguredError()
    return _whisper_client(nutrition_settings.openai_api_key)


@cache
def _whisper_client(api_key: str) -> TranscriptionClient:
    return OpenAIWhisperClient(api_key=api_key)
