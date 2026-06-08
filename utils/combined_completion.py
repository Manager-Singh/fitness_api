"""
Bug 11 — combined Lifestyle + Habits completion percentage.

Per HEIGHT_APP_COMPLETE_BUILD_DOC_v4 the dashboard completion indicator must combine
BOTH the lifestyle items AND the habit points into ONE shared number, and only reach
100% when everything is done:

    completion_pct = (lifestyle_earned + habits_earned) / (lifestyle_max + habits_max) * 100

Teen worked example: lifestyle max = sleep 10 + water 10 + sunlight 7 + meditation 2 = 29,
habits max = 12 (the corrected daily habits cap), total possible = 41. Logging all
lifestyle (29) but no habits (0) gives 29/41 = 71%, NOT 100%.

For ADULTS (no Lifestyle tab) the spec combines their nutrition/hydration completion
(Part 2: protein + hydration, max 15) with habits (max 12) → total possible 27.

This is a DISPLAY metric: the per-channel maxes below are decoupled from the Engine-1 /
Engine-2 height caps (GLOBAL DO-NOT-TOUCH), so the bar can actually reach 100% when a
user completes everything.
"""
from __future__ import annotations

from habits.services import DAILY_HABIT_CAP, capped_habit_points_for_engine
from utils.teen_dashboard_dots import teen_lifestyle_channel_scores

# Teen lifestyle completion maxes (display scale; sum = 29).
TEEN_LIFESTYLE_COMPLETION_MAX = {
    "sleep": 10,
    "water": 10,
    "sunlight": 7,
    "meditation": 2,
}
TEEN_LIFESTYLE_MAX_POINTS = sum(TEEN_LIFESTYLE_COMPLETION_MAX.values())  # 29

# Adult nutrition completion max (Part 2: protein 9 + hydration 6).
ADULT_NUTRITION_COMPLETION_MAX = 15

# Habits completion max = the daily habits cap (12 after Part 3).
HABITS_COMPLETION_MAX = DAILY_HABIT_CAP


def _pct(earned: float, total: float) -> int:
    if total <= 0:
        return 0
    return int(round(min(100.0, max(0.0, (float(earned) / float(total)) * 100.0))))


def teen_lifestyle_completion_earned(user, log_date) -> int:
    """
    Lifestyle points earned (0..29) on the completion scale. A channel contributes its
    full completion-max once its logging threshold is met (same thresholds as the
    lifestyle dots), so fully logging lifestyle yields the full 29.
    """
    s = teen_lifestyle_channel_scores(user, log_date)
    earned = 0
    if s["sleep"] >= 5.0:
        earned += TEEN_LIFESTYLE_COMPLETION_MAX["sleep"]
    if s["hyd"] >= 1.0:
        earned += TEEN_LIFESTYLE_COMPLETION_MAX["water"]
    if s["sun"] >= 6.0:
        earned += TEEN_LIFESTYLE_COMPLETION_MAX["sunlight"]
    if s["med"] >= 1.0:
        earned += TEEN_LIFESTYLE_COMPLETION_MAX["meditation"]
    return earned


def habits_completion_earned(user, log_date) -> int:
    """Habit points earned for the day, capped at the daily habits cap (Engine-1 scale)."""
    return int(capped_habit_points_for_engine(user, log_date))


def teen_combined_completion(user, log_date) -> dict:
    """Teen combined Lifestyle (29) + Habits (12) completion."""
    lifestyle_earned = teen_lifestyle_completion_earned(user, log_date)
    habits_earned = habits_completion_earned(user, log_date)
    total_possible = TEEN_LIFESTYLE_MAX_POINTS + HABITS_COMPLETION_MAX
    return {
        "lifestyle_earned": lifestyle_earned,
        "lifestyle_max": TEEN_LIFESTYLE_MAX_POINTS,
        "habits_earned": habits_earned,
        "habits_max": HABITS_COMPLETION_MAX,
        "earned": lifestyle_earned + habits_earned,
        "total_possible": total_possible,
        "percent": _pct(lifestyle_earned + habits_earned, total_possible),
    }


def _adult_nutrition_completion_earned(user, log_date) -> int:
    """
    Adult nutrition points earned (0..15) for the day.

    Primary source is the Part 2 protein+hydration model (AdultNutritionDay). When that
    has no data for the day (e.g. the client still logs via the legacy disc/muscle food
    UI), fall back to the legacy food-list completion (0/50/100) mapped onto the 15-pt
    scale so already-logged nutrition still counts toward the dashboard bar.
    """
    try:
        from utils.adult_nutrition import (
            adult_food_completion_percent_legacy,
            adult_nutrition_points_today,
        )

        pts = int(adult_nutrition_points_today(user, log_date))
        if pts > 0:
            return min(ADULT_NUTRITION_COMPLETION_MAX, pts)
        legacy_pct = int(adult_food_completion_percent_legacy(user, log_date))
        return int(round(ADULT_NUTRITION_COMPLETION_MAX * (legacy_pct / 100.0)))
    except Exception:
        return 0


def adult_combined_completion(user, log_date) -> dict:
    """Adult combined Nutrition/Hydration (15) + Habits (12) completion (no Lifestyle tab)."""
    nutrition_earned = _adult_nutrition_completion_earned(user, log_date)
    habits_earned = habits_completion_earned(user, log_date)
    total_possible = ADULT_NUTRITION_COMPLETION_MAX + HABITS_COMPLETION_MAX
    return {
        "nutrition_earned": nutrition_earned,
        "nutrition_max": ADULT_NUTRITION_COMPLETION_MAX,
        "habits_earned": habits_earned,
        "habits_max": HABITS_COMPLETION_MAX,
        "earned": nutrition_earned + habits_earned,
        "total_possible": total_possible,
        "percent": _pct(nutrition_earned + habits_earned, total_possible),
    }


def combined_completion_for_user(user, log_date, *, is_teen: bool) -> dict:
    return teen_combined_completion(user, log_date) if is_teen else adult_combined_completion(user, log_date)
