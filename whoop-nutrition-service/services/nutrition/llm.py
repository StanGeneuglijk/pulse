"""The chat provider seam: chat.py depends on `ChatLLMClient`, never on a vendor
SDK. A turn ends in a plain reply, a structured meal proposal, or both.
"""

from dataclasses import dataclass
from typing import Literal, Protocol

Role = Literal["user", "assistant"]
Effort = Literal["low", "medium", "high", "xhigh", "max"]


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str


@dataclass(frozen=True)
class MealItemProposal:
    name: str
    quantity: str
    calories: int
    protein_g: float
    carbs_g: float
    fat_g: float


@dataclass(frozen=True)
class MealProposal:
    description: str
    logged_at: str  # naive-UTC ISO 8601, normalized at the provider boundary
    items: list[MealItemProposal]
    total_calories: int
    total_protein_g: float
    total_carbs_g: float
    total_fat_g: float
    fiber_g: float | None = None
    sugar_g: float | None = None
    sodium_mg: float | None = None


@dataclass(frozen=True)
class ChatResult:
    text: str | None
    tool_call: MealProposal | None
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


# Never forced (tool_choice stays "auto"), so Claude asks a clarifying
# question instead of guessing; `strict` guarantees schema-valid input.
PROPOSE_MEAL_BREAKDOWN_TOOL: dict = {
    "name": "propose_meal_breakdown",
    "description": (
        "Propose a structured nutritional breakdown for a meal the user has described in "
        "enough detail to estimate. Do not call this if you need more detail first — ask a "
        "clarifying question in plain text instead."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "Short summary of the meal."},
            "loggedAt": {
                "type": "string",
                "description": "ISO 8601 datetime the meal was eaten, resolved from context "
                "(e.g. 'this morning') against today's date.",
            },
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "quantity": {"type": "string"},
                        "calories": {"type": "integer"},
                        "proteinG": {"type": "number"},
                        "carbsG": {"type": "number"},
                        "fatG": {"type": "number"},
                    },
                    "required": ["name", "quantity", "calories", "proteinG", "carbsG", "fatG"],
                    "additionalProperties": False,
                },
            },
            "totalCalories": {"type": "integer"},
            "totalProteinG": {"type": "number"},
            "totalCarbsG": {"type": "number"},
            "totalFatG": {"type": "number"},
            "fiberG": {"type": ["number", "null"]},
            "sugarG": {"type": ["number", "null"]},
            "sodiumMg": {"type": ["number", "null"]},
        },
        "required": [
            "description",
            "loggedAt",
            "items",
            "totalCalories",
            "totalProteinG",
            "totalCarbsG",
            "totalFatG",
        ],
        "additionalProperties": False,
    },
    "strict": True,
}


class ChatLLMClient(Protocol):
    """Turns a system prompt + history into a reply and/or a
    `propose_meal_breakdown` call.
    """

    async def send(
        self,
        *,
        system: str,
        messages: list[ChatMessage],
        max_tokens: int,
        effort: Effort,
    ) -> ChatResult: ...
