"""The only module that calls Anthropic. Maps the response to `LLMResult` and
every SDK error to `LLMProviderError`, so nothing upstream sees vendor types.
"""

from anthropic import APIError, AsyncAnthropic

from services.insight.config import LLM_MAX_RETRIES, LLM_TIMEOUT_SECONDS
from services.insight.exceptions import LLMProviderError
from services.insight.llm import Effort, LLMResult


class AnthropicLLMClient:
    def __init__(self, *, api_key: str, model: str) -> None:
        self._client = AsyncAnthropic(
            api_key=api_key, timeout=LLM_TIMEOUT_SECONDS, max_retries=LLM_MAX_RETRIES
        )
        self._model = model

    async def generate(
        self, *, system: str, user_prompt: str, max_tokens: int, effort: Effort
    ) -> LLMResult:
        """One Messages API call. `effort` is the reasoning lever; thinking is left
        unset (adaptive by default on this model family).

        Raises:
            LLMProviderError: If the call fails or returns no text.
        """
        try:
            message = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user_prompt}],
                output_config={"effort": effort},
            )
        except APIError as exc:
            raise LLMProviderError(str(exc)) from exc

        # Thinking counts toward max_tokens: a reply cut off there is an insight
        # that stops mid-sentence. Fail rather than store it as complete.
        if message.stop_reason == "max_tokens":
            raise LLMProviderError(
                f"reply cut off at max_tokens ({max_tokens}, "
                f"{message.usage.output_tokens} output tokens)"
            )

        text = "".join(block.text for block in message.content if block.type == "text")
        if not text:
            raise LLMProviderError("response contained no text content")

        return LLMResult(
            text=text,
            model=message.model,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )
