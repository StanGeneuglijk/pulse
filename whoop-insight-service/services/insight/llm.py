"""The provider seam: generate.py depends on `LLMClient`, never on a vendor SDK."""

from dataclasses import dataclass
from typing import Literal, Protocol

Effort = Literal["low", "medium", "high", "xhigh", "max"]


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMClient(Protocol):
    """Turns a system + user prompt into text under an explicit output-token
    ceiling and effort level. Every implementation must honor both.
    """

    async def generate(
        self, *, system: str, user_prompt: str, max_tokens: int, effort: Effort
    ) -> LLMResult: ...
