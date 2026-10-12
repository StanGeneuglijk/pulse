"""Selects the concrete LLMClient this deployment runs — today always
Anthropic. A second provider is a new module here plus one branch below;
generate.py never changes.
"""

from functools import cache

from services.insight.config import insight_settings
from services.insight.llm import LLMClient
from services.insight.providers.anthropic_client import AnthropicLLMClient


@cache
def get_llm_client() -> LLMClient:
    """One client per process, so its HTTP connection pool is reused."""
    return AnthropicLLMClient(
        api_key=insight_settings.anthropic_api_key,
        model=insight_settings.llm_model,
    )
