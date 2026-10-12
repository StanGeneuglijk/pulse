from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from anthropic import APIError

from services.nutrition.exceptions import LLMProviderError
from services.nutrition.llm import ChatMessage
from services.nutrition.providers.anthropic_client import AnthropicChatClient


def _text_message(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason="end_turn",
        model="claude-sonnet-5",
        usage=SimpleNamespace(input_tokens=20, output_tokens=8),
    )


def _tool_call_message(
    logged_at: str = "2026-09-27T08:00:00", stop_reason: str = "tool_use"
) -> SimpleNamespace:
    tool_input = {
        "description": "Two eggs and toast",
        "loggedAt": logged_at,
        "items": [
            {
                "name": "egg",
                "quantity": "2 large",
                "calories": 140,
                "proteinG": 12.0,
                "carbsG": 1.0,
                "fatG": 10.0,
            }
        ],
        "totalCalories": 140,
        "totalProteinG": 12.0,
        "totalCarbsG": 1.0,
        "totalFatG": 10.0,
    }
    return SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="Here's what I calculated:"),
            SimpleNamespace(type="tool_use", name="propose_meal_breakdown", input=tool_input),
        ],
        stop_reason=stop_reason,
        model="claude-sonnet-5",
        usage=SimpleNamespace(input_tokens=30, output_tokens=15),
    )


async def test_send_parses_a_text_only_reply():
    client = AnthropicChatClient(api_key="test-key", model="claude-sonnet-5")
    client._client.messages.create = AsyncMock(return_value=_text_message("What size portion?"))

    result = await client.send(
        system="sys", messages=[ChatMessage(role="user", content="I had a burrito")],
        max_tokens=400, effort="low",
    )

    assert result.text == "What size portion?"
    assert result.tool_call is None
    assert result.input_tokens == 20


async def test_send_parses_a_tool_call_reply():
    client = AnthropicChatClient(api_key="test-key", model="claude-sonnet-5")
    client._client.messages.create = AsyncMock(return_value=_tool_call_message())

    result = await client.send(
        system="sys", messages=[ChatMessage(role="user", content="two eggs and toast")],
        max_tokens=400, effort="low",
    )

    assert result.text == "Here's what I calculated:"
    assert result.tool_call is not None
    assert result.tool_call.description == "Two eggs and toast"
    assert result.tool_call.items[0].name == "egg"
    assert result.tool_call.total_calories == 140


async def test_send_wraps_an_api_error():
    client = AnthropicChatClient(api_key="test-key", model="claude-sonnet-5")
    client._client.messages.create = AsyncMock(
        side_effect=APIError("boom", request=SimpleNamespace(), body=None)
    )

    with pytest.raises(LLMProviderError):
        await client.send(
            system="sys", messages=[ChatMessage(role="user", content="hi")],
            max_tokens=400, effort="low",
        )


@pytest.mark.parametrize(
    ("logged_at", "expected"),
    [
        ("2026-09-27T08:00:00+02:00", "2026-09-27T06:00:00"),  # offset converted, not dropped
        ("2026-09-27T08:00:00Z", "2026-09-27T08:00:00"),
        ("2026-09-27T08:00:00", "2026-09-27T08:00:00"),  # no offset means UTC
    ],
)
async def test_send_normalizes_logged_at_to_naive_utc(logged_at, expected):
    client = AnthropicChatClient(api_key="test-key", model="claude-sonnet-5")
    client._client.messages.create = AsyncMock(return_value=_tool_call_message(logged_at))

    result = await client.send(
        system="sys", messages=[ChatMessage(role="user", content="two eggs")],
        max_tokens=400, effort="low",
    )

    assert result.tool_call is not None
    assert result.tool_call.logged_at == expected


async def test_send_rejects_a_malformed_logged_at():
    client = AnthropicChatClient(api_key="test-key", model="claude-sonnet-5")
    client._client.messages.create = AsyncMock(return_value=_tool_call_message("this morning"))

    with pytest.raises(LLMProviderError):
        await client.send(
            system="sys", messages=[ChatMessage(role="user", content="two eggs")],
            max_tokens=400, effort="low",
        )


async def test_send_rejects_a_reply_cut_off_at_max_tokens():
    # Thinking counts toward max_tokens, so a long breakdown can be cut off mid
    # tool call. Even a partial input that happens to parse must not be trusted.
    client = AnthropicChatClient(api_key="test-key", model="claude-sonnet-5")
    client._client.messages.create = AsyncMock(
        return_value=_tool_call_message(stop_reason="max_tokens")
    )

    with pytest.raises(LLMProviderError, match="max_tokens"):
        await client.send(
            system="sys", messages=[ChatMessage(role="user", content="two eggs and toast")],
            max_tokens=400, effort="low",
        )
