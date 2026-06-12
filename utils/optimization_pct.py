"""
Friday work order Task 1 — daily optimization % from one shared point pool.

Teen pool = 68 (nutrition 35 + lifestyle 21 + habits 12).
Adult pool = 27 (nutrition 15 + habits 12; no Lifestyle tab).

Display-only metric: does not touch engines, ledger, or point-to-cm conversion.
"""
from __future__ import annotations

from habits.services import DAILY_HABIT_CAP

TEEN_NUTRITION_CAP = 35
TEEN_LIFESTYLE_CAP = 21
TEEN_HABITS_CAP = DAILY_HABIT_CAP  # 12
TEEN_POOL = TEEN_NUTRITION_CAP + TEEN_LIFESTYLE_CAP + TEEN_HABITS_CAP  # 68

ADULT_NUTRITION_CAP = 15
ADULT_HABITS_CAP = DAILY_HABIT_CAP  # 12
ADULT_POOL = ADULT_NUTRITION_CAP + ADULT_HABITS_CAP  # 27


def _pct(earned: float, total: float) -> int:
    if total <= 0:
        return 0
    return int(round(min(100.0, max(0.0, (float(earned) / float(total)) * 100.0))))


def _cap(value, maximum: int) -> int:
    return int(min(maximum, max(0, int(value or 0))))


def daily_optimization_from_breakdown(breakdown: dict | None, *, is_teen: bool) -> dict:
    """
    Compute optimization % from today's score breakdown (post-cap section totals).

    ``breakdown`` keys: food_score, activity_score (lifestyle), habit_score.
    Workouts are excluded from the optimization pool.
    """
    bd = breakdown or {}
    habits = _cap(bd.get("habit_score"), TEEN_HABITS_CAP if is_teen else ADULT_HABITS_CAP)

    if is_teen:
        nutrition = _cap(bd.get("food_score"), TEEN_NUTRITION_CAP)
        lifestyle = _cap(bd.get("activity_score") or bd.get("lifestyle_score"), TEEN_LIFESTYLE_CAP)
        earned = nutrition + lifestyle + habits
        total_possible = TEEN_POOL
        return {
            "nutrition_earned": nutrition,
            "nutrition_max": TEEN_NUTRITION_CAP,
            "lifestyle_earned": lifestyle,
            "lifestyle_max": TEEN_LIFESTYLE_CAP,
            "habits_earned": habits,
            "habits_max": TEEN_HABITS_CAP,
            "earned": earned,
            "total_possible": total_possible,
            "percent": _pct(earned, total_possible),
            "pool": TEEN_POOL,
        }

    nutrition = _cap(bd.get("food_score"), ADULT_NUTRITION_CAP)
    earned = nutrition + habits
    total_possible = ADULT_POOL
    return {
        "nutrition_earned": nutrition,
        "nutrition_max": ADULT_NUTRITION_CAP,
        "habits_earned": habits,
        "habits_max": ADULT_HABITS_CAP,
        "earned": earned,
        "total_possible": total_possible,
        "percent": _pct(earned, total_possible),
        "pool": ADULT_POOL,
    }


def daily_optimization_for_user(user, log_date, *, is_teen: bool, subscription_data=None) -> dict:
    """Load today's breakdown and compute optimization %."""
    from utils.check_payment import check_subscription_or_response
    from utils.scores_summary import today_score_breakdown

    sub = subscription_data
    if sub is None:
        sub = check_subscription_or_response(user).data
    breakdown = today_score_breakdown(user, sub)
    return daily_optimization_from_breakdown(breakdown, is_teen=is_teen)
