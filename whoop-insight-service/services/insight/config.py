"""Insight-specific settings and policy: the model, per-period effort and token
limits, spend caps, and lock/timeout constants.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from services.insight.pricing import PRICE_PER_MTOK_USD

InsightPeriod = Literal["daily", "weekly", "monthly"]


class InsightSettings(BaseSettings):
    anthropic_api_key: str
    llm_model: str = "claude-sonnet-5"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("llm_model")
    @classmethod
    def _validate_known_priced_model(cls, value: str) -> str:
        """Reject a model pricing.py can't cost, at startup — the spend cap is only
        as accurate as that table.
        """
        if value not in PRICE_PER_MTOK_USD:
            raise ValueError(
                f"{value!r} is not in pricing.PRICE_PER_MTOK_USD — add its rate there first, "
                "so services/insight/crud.py's spend cap can price it correctly"
            )
        return value


insight_settings = InsightSettings()  # type: ignore[call-arg]  # values come from the environment


# Part of an insight's idempotency key: a prompt rewrite is a new generation,
# not an overwrite of what the old prompt produced.
PROMPT_VERSION = "v1"

# One LLM call's worst case is LLM_TIMEOUT_SECONDS x (1 + LLM_MAX_RETRIES)
# — the per-user lock TTL must outlast that, or a slow call loses its lock
# and a second request pays for a duplicate generation.
LLM_TIMEOUT_SECONDS = 50.0
LLM_MAX_RETRIES = 1
INSIGHT_LOCK_TTL_SECONDS = 120

# Spend caps, checked before every call: per user first (the everyday quota,
# so one heavy user only locks out themselves), then platform-wide (the
# "something is badly wrong" backstop). Estimates from pricing.py.
INSIGHT_PER_USER_SPEND_LIMIT_USD = 1.00
INSIGHT_SPEND_LIMIT_USD = 5.00


@dataclass(frozen=True)
class PeriodPolicy:
    window_days: int
    effort: Literal["low", "medium", "high", "xhigh", "max"]
    max_output_tokens: int


# The caller picks a period, never effort or tokens: short windows get low
# effort, the monthly roll-up gets more. max_output_tokens is a ceiling, not a
# length: the prompt asks for 3-5 sentences, and only generated tokens are
# billed. It must also cover the model's thinking, which counts toward it (even
# unshown) and grows with effort; at 512/768/1024 a high-effort reply could be
# cut off mid-sentence.
PERIOD_POLICY: dict[InsightPeriod, PeriodPolicy] = {
    "daily": PeriodPolicy(window_days=1, effort="low", max_output_tokens=4000),
    "weekly": PeriodPolicy(window_days=7, effort="medium", max_output_tokens=8000),
    "monthly": PeriodPolicy(window_days=30, effort="high", max_output_tokens=16000),
}
