"""System + user prompt from the data windows. Text only: no I/O, no provider."""

from services.insight.config import InsightPeriod
from services.insight.nutrition_read import ActiveGoal, NutritionWindow
from services.insight.whoop_read import WhoopWindow

_PERIOD_FRAMING: dict[InsightPeriod, str] = {
    "daily": "a quick daily check-in — one day's data, keep it brief and immediate",
    "weekly": "a weekly recap — look for the trend across the week, not just the latest day",
    "monthly": "a monthly rollup — focus on the overall trend, not day-to-day noise",
}


def _system_prompt(period: InsightPeriod, *, has_nutrition: bool) -> str:
    nutrition_clause = (
        " You're also given what they ate over the same period — correlate it with "
        "recovery/sleep/strain where it's genuinely relevant (e.g. under-eating on "
        "high-strain days), but don't force a connection that isn't there."
        if has_nutrition
        else ""
    )
    return (
        "You are a sports-science assistant. Given a person's recent WHOOP "
        "recovery, sleep, and workout-strain scores, write a short, plain-"
        f"language insight (3-5 sentences) framed as {_PERIOD_FRAMING[period]}."
        f"{nutrition_clause} End with one concrete, actionable suggestion. No "
        "medical claims. No disclaimers about not being a doctor — just the insight."
    )


def build_user_prompt(
    window: WhoopWindow,
    *,
    nutrition_window: NutritionWindow | None = None,
    active_goal: ActiveGoal | None = None,
) -> str:
    lines = ["Recovery scores (0-100, by date):"]
    lines += [f"- {r.recorded_at.date()}: {r.score}" for r in window.recovery] or ["- none"]
    lines.append("\nSleep performance scores (0-100, by date):")
    lines += [f"- {r.recorded_at.date()}: {r.score}" for r in window.sleep] or ["- none"]
    lines.append("\nWorkout strain scores (0-21, by date):")
    lines += [f"- {r.recorded_at.date()}: {r.score}" for r in window.workout] or ["- none"]

    # Omitted entirely when empty — an empty heading invites the model to
    # comment on the absence.
    if nutrition_window is not None and not nutrition_window.is_empty():
        lines.append("\nMeals logged this period (calories, by date):")
        lines += [
            f"- {m.logged_at.date()}: {m.calories} kcal "
            f"({m.protein_g:.0f}g protein, {m.carbs_g:.0f}g carbs, {m.fat_g:.0f}g fat)"
            for m in sorted(nutrition_window.meals, key=lambda m: m.logged_at)
        ]

    if active_goal is not None:
        targets = []
        if active_goal.target_calories is not None:
            targets.append(f"{active_goal.target_calories} kcal/day")
        if active_goal.target_protein_g is not None:
            targets.append(f"{active_goal.target_protein_g:.0f}g protein/day")
        target_text = ", ".join(targets) if targets else "no numeric targets"
        lines.append(f"\nTheir goal is {active_goal.goal_type} ({target_text}).")

    return "\n".join(lines)


def build_prompt(
    window: WhoopWindow,
    period: InsightPeriod,
    *,
    nutrition_window: NutritionWindow | None = None,
    active_goal: ActiveGoal | None = None,
) -> tuple[str, str]:
    """Returns `(system, user_prompt)` for `LLMClient.generate`."""
    has_nutrition = nutrition_window is not None and not nutrition_window.is_empty()
    return (
        _system_prompt(period, has_nutrition=has_nutrition),
        build_user_prompt(window, nutrition_window=nutrition_window, active_goal=active_goal),
    )
