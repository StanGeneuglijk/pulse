from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from anthropic import APIError

from services.insight.exceptions import LLMProviderError
from services.insight.providers.anthropic_client import AnthropicLLMClient


def _fake_message(text: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        model="claude-sonnet-5",
        usage=SimpleNamespace(input_tokens=42, output_tokens=7),
    )


async def test_generate_parses_text_and_usage_from_the_response():
    client = AnthropicLLMClient(api_key="test-key", model="claude-sonnet-5")
    client._client.messages.create = AsyncMock(return_value=_fake_message("Great recovery."))

    result = await client.generate(system="sys", user_prompt="user", max_tokens=512, effort="low")

    assert result.text == "Great recovery."
    assert result.model == "claude-sonnet-5"
    assert result.input_tokens == 42
    assert result.output_tokens == 7
    call_kwargs = client._client.messages.create.call_args.kwargs
    assert call_kwargs["max_tokens"] == 512
    assert call_kwargs["output_config"] == {"effort": "low"}


async def test_generate_wraps_an_api_error_as_llm_provider_error():
    client = AnthropicLLMClient(api_key="test-key", model="claude-sonnet-5")
    client._client.messages.create = AsyncMock(
        side_effect=APIError("boom", request=SimpleNamespace(), body=None)
    )

    with pytest.raises(LLMProviderError):
        await client.generate(system="sys", user_prompt="user", max_tokens=512, effort="low")


async def test_generate_rejects_a_response_with_no_text_blocks():
    client = AnthropicLLMClient(api_key="test-key", model="claude-sonnet-5")
    empty_message = SimpleNamespace(
        content=[],
        stop_reason="end_turn",
        model="claude-sonnet-5",
        usage=SimpleNamespace(input_tokens=1, output_tokens=0),
    )
    client._client.messages.create = AsyncMock(return_value=empty_message)

    with pytest.raises(LLMProviderError):
        await client.generate(system="sys", user_prompt="user", max_tokens=512, effort="low")


async def test_generate_rejects_a_reply_cut_off_at_max_tokens():
    # Thinking counts toward max_tokens; a reply cut off there is an insight that
    # stops mid-sentence. It must fail, never be stored as if it were complete.
    client = AnthropicLLMClient(api_key="test-key", model="claude-sonnet-5")
    client._client.messages.create = AsyncMock(
        return_value=_fake_message("Your recovery trended up while", stop_reason="max_tokens")
    )

    with pytest.raises(LLMProviderError, match="max_tokens"):
        await client.generate(system="sys", user_prompt="user", max_tokens=512, effort="high")
