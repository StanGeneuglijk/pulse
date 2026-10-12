"""Nutrition-specific settings and policy: chat and transcription models,
spend caps, context and request bounds, lock/timeout constants.
"""

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from services.nutrition.llm import Effort
from services.nutrition.pricing import PRICE_PER_MTOK_USD, WHISPER_PRICE_PER_MINUTE_USD

NutritionPeriod = Literal["daily", "weekly", "monthly"]


class NutritionSettings(BaseSettings):
    anthropic_api_key: str
    llm_model: str = "claude-sonnet-5"
    # Optional: only the audio route needs it.
    openai_api_key: str | None = None
    transcription_model: str = "whisper-1"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("llm_model")
    @classmethod
    def _validate_known_priced_model(cls, value: str) -> str:
        """Reject a chat model pricing.py can't cost, at startup."""
        if value not in PRICE_PER_MTOK_USD:
            raise ValueError(
                f"{value!r} is not in pricing.PRICE_PER_MTOK_USD — add its rate there first, "
                "so services/nutrition/crud.py's spend cap can price it correctly"
            )
        return value

    @field_validator("transcription_model")
    @classmethod
    def _validate_known_priced_transcription_model(cls, value: str) -> str:
        """Reject a transcription model pricing.py can't cost, at startup."""
        if value not in WHISPER_PRICE_PER_MINUTE_USD:
            raise ValueError(
                f"{value!r} is not in pricing.WHISPER_PRICE_PER_MINUTE_USD — add its rate "
                "there first, so services/nutrition/crud.py's spend cap can price it correctly"
            )
        return value


nutrition_settings = NutritionSettings()  # type: ignore[call-arg]  # values come from the environment


# Recorded for provenance; unlike insights, a confirmed meal isn't re-generatable.
PROMPT_VERSION = "v1"

# One provider call's worst case is LLM_TIMEOUT_SECONDS x (1 + LLM_MAX_RETRIES)
# — the per-conversation lock TTL must outlast that, or a slow turn loses
# its lock and a double-submit interleaves two replies.
LLM_TIMEOUT_SECONDS = 50.0
LLM_MAX_RETRIES = 1
NUTRITION_LOCK_TTL_SECONDS = 120

# Request bounds: message length caps per-turn input tokens; the audio cap
# sits under OpenAI's 25 MB transcription limit.
NUTRITION_MAX_MESSAGE_CHARS = 2000
NUTRITION_MAX_AUDIO_BYTES = 10 * 1024 * 1024

# Spend caps over chat + transcription, checked before every paid call: per
# user first (the everyday quota), then platform-wide (the backstop).
NUTRITION_PER_USER_SPEND_LIMIT_USD = 1.00
NUTRITION_SPEND_LIMIT_USD = 5.00


# A turn resends history, so cost grows with conversation length — bound it.
NUTRITION_CONTEXT_MESSAGE_LIMIT = 20

# A chat reply needs neither deep reasoning nor length.
NUTRITION_CHAT_EFFORT: Effort = "low"
# A ceiling, not a target: only generated tokens are billed. It must cover the
# model's thinking (which counts toward it, even unshown) plus a multi-item
# meal breakdown; at 400 long breakdowns were cut off mid tool call.
NUTRITION_CHAT_MAX_TOKENS = 4000

# Same period vocabulary as whoop-insight-service, for the summary endpoint.
NUTRITION_PERIOD_WINDOW_DAYS: dict[NutritionPeriod, int] = {
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
}
