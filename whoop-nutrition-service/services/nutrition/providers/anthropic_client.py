"""The only module that calls Anthropic for chat. Maps a response to `ChatResult`
(text and/or a typed MealProposal) and every SDK error to `LLMProviderError`.
"""

from datetime import UTC, datetime
from typing import Any, cast

from anthropic import APIError, AsyncAnthropic

from services.nutrition.config import LLM_MAX_RETRIES, LLM_TIMEOUT_SECONDS
from services.nutrition.exceptions import LLMProviderError
from services.nutrition.llm import (
    PROPOSE_MEAL_BREAKDOWN_TOOL,
    ChatMessage,
    ChatResult,
    Effort,
    MealItemProposal,
    MealProposal,
)

_TOOL_NAME = "propose_meal_breakdown"


def _naive_utc_iso(value: str) -> str:
    """The model's `loggedAt` as naive UTC — the form every timestamp in this
    schema uses. An offset is converted, not dropped; no offset means UTC.

    Raises:
        ValueError: If `value` isn't ISO 8601.
    """
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed.isoformat()


def _parse_meal_proposal(tool_input: dict) -> MealProposal:
    return MealProposal(
        description=tool_input["description"],
        logged_at=_naive_utc_iso(tool_input["loggedAt"]),
        items=[
            MealItemProposal(
                name=item["name"],
                quantity=item["quantity"],
                calories=item["calories"],
                protein_g=item["proteinG"],
                carbs_g=item["carbsG"],
                fat_g=item["fatG"],
            )
            for item in tool_input["items"]
        ],
        total_calories=tool_input["totalCalories"],
        total_protein_g=tool_input["totalProteinG"],
        total_carbs_g=tool_input["totalCarbsG"],
        total_fat_g=tool_input["totalFatG"],
        fiber_g=tool_input.get("fiberG"),
        sugar_g=tool_input.get("sugarG"),
        sodium_mg=tool_input.get("sodiumMg"),
    )


class AnthropicChatClient:
    def __init__(self, *, api_key: str, model: str) -> None:
        self._client = AsyncAnthropic(
            api_key=api_key, timeout=LLM_TIMEOUT_SECONDS, max_retries=LLM_MAX_RETRIES
        )
        self._model = model

    async def send(
        self, *, system: str, messages: list[ChatMessage], max_tokens: int, effort: Effort
    ) -> ChatResult:
        """One Messages API call with the propose_meal_breakdown tool available.

        Raises:
            LLMProviderError: If the call fails or the tool input is malformed.
        """
        try:
            message = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                # A plain dict keeps llm.py SDK-free; cast for the SDK's param type.
                tools=cast(Any, [PROPOSE_MEAL_BREAKDOWN_TOOL]),
                output_config={"effort": effort},
            )
        except APIError as exc:
            raise LLMProviderError(str(exc)) from exc

        # Thinking counts toward max_tokens: a reply cut off there can hold a tool
        # call missing its later fields, which may still parse. Never trust it.
        if message.stop_reason == "max_tokens":
            raise LLMProviderError(
                f"reply cut off at max_tokens ({max_tokens}, "
                f"{message.usage.output_tokens} output tokens)"
            )

        text_parts = [block.text for block in message.content if block.type == "text"]
        tool_call = None
        for block in message.content:
            if block.type == "tool_use" and block.name == _TOOL_NAME:
                try:
                    tool_call = _parse_meal_proposal(block.input)
                except (KeyError, TypeError, ValueError) as exc:
                    raise LLMProviderError(f"malformed tool call: {exc}") from exc
                break

        return ChatResult(
            text="".join(text_parts) or None,
            tool_call=tool_call,
            model=message.model,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )
