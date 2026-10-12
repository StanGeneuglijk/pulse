"""The chat system prompt: behavior rules, today's date (so "this morning"
resolves), and the active goal. Text only: no I/O, no provider.
"""

from core.clock import utcnow
from services.nutrition.models import NutritionGoal

_BASE_PROMPT = (
    "You are a friendly nutrition assistant. The user will describe meals in "
    "conversation. When you have enough detail to reasonably estimate the "
    "nutrition (what the food is, roughly how much), call propose_meal_breakdown "
    "with your best estimate. If you don't have enough detail yet (e.g. unclear "
    "portion size, an ambiguous dish), ask one short clarifying question in plain "
    "text instead of guessing — do not call the tool until you have enough to "
    "estimate from.\n\n"
    "Estimates are approximate, for personal trend-tracking, not clinical "
    "precision — say so only if asked, don't caveat every message."
)


def build_system_prompt(*, active_goal: NutritionGoal | None) -> str:
    parts = [_BASE_PROMPT, f"\nToday's date is {utcnow().date().isoformat()}."]
    if active_goal is not None:
        targets = []
        if active_goal.target_calories is not None:
            targets.append(f"{active_goal.target_calories} kcal/day")
        if active_goal.target_protein_g is not None:
            targets.append(f"{active_goal.target_protein_g:.0f}g protein/day")
        if active_goal.target_carbs_g is not None:
            targets.append(f"{active_goal.target_carbs_g:.0f}g carbs/day")
        if active_goal.target_fat_g is not None:
            targets.append(f"{active_goal.target_fat_g:.0f}g fat/day")
        target_text = ", ".join(targets) if targets else "no numeric targets set"
        parts.append(
            f"\nThe user's active goal is {active_goal.goal_type} ({target_text})."
            f" You may naturally reference progress toward this when relevant, but "
            f"don't force it into every reply."
        )
        if active_goal.notes:
            parts.append(f"Additional context on their goal: {active_goal.notes}")
    return "\n".join(parts)
