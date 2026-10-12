from datetime import datetime

from services.insight.nutrition_read import ActiveGoal, NutritionRecord, NutritionWindow
from services.insight.prompt import build_prompt, build_user_prompt
from services.insight.whoop_read import WhoopWindow


def _whoop_window() -> WhoopWindow:
    return WhoopWindow(recovery=[], sleep=[], workout=[])


def test_prompt_omits_nutrition_section_when_theres_nothing_to_add():
    """task 11's acceptance: a user who's never logged a meal or set a
    goal gets exactly the pre-integration prompt — no empty heading, no
    error."""
    user_prompt = build_user_prompt(_whoop_window())

    assert "Meals logged" not in user_prompt
    assert "goal" not in user_prompt.lower()

    system, _ = build_prompt(_whoop_window(), "weekly")
    assert "eat" not in system.lower() and "nutrition" not in system.lower()


def test_prompt_includes_a_nutrition_section_when_meals_exist():
    window = NutritionWindow(
        meals=[
            NutritionRecord(
                calories=450,
                protein_g=49.0,
                carbs_g=44.0,
                fat_g=6.5,
                logged_at=datetime(2026, 9, 20, 12, 0),
            )
        ]
    )

    user_prompt = build_user_prompt(_whoop_window(), nutrition_window=window)

    assert "Meals logged this period" in user_prompt
    assert "450 kcal" in user_prompt

    system, _ = build_prompt(_whoop_window(), "weekly", nutrition_window=window)
    assert "ate" in system.lower() or "correlate" in system.lower()


def test_prompt_includes_a_goal_progress_line_when_a_goal_exists():
    goal = ActiveGoal(
        goal_type="weight_loss",
        target_calories=1800,
        target_protein_g=140.0,
        target_carbs_g=None,
        target_fat_g=None,
    )

    user_prompt = build_user_prompt(_whoop_window(), active_goal=goal)

    assert "weight_loss" in user_prompt
    assert "1800 kcal/day" in user_prompt


def test_prompt_skips_the_nutrition_section_for_an_empty_window():
    """An empty NutritionWindow (the table exists, but this user has no
    rows in it) must degrade exactly like no window at all — not an
    empty heading."""
    empty_window = NutritionWindow(meals=[])

    user_prompt = build_user_prompt(_whoop_window(), nutrition_window=empty_window)

    assert "Meals logged" not in user_prompt
