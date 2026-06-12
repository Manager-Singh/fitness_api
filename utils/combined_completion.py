"""
Daily optimization % — delegates to Friday work order Task 1 pool (68 teen / 27 adult).

Kept for backward compatibility with imports; ``combined_completion_for_user`` is the
primary entry point used by dashboard-new.
"""
from __future__ import annotations

from utils.optimization_pct import (
    ADULT_NUTRITION_CAP as ADULT_NUTRITION_COMPLETION_MAX,
    ADULT_POOL,
    TEEN_HABITS_CAP as HABITS_COMPLETION_MAX,
    TEEN_LIFESTYLE_CAP as TEEN_LIFESTYLE_MAX_POINTS,
    TEEN_NUTRITION_CAP,
    TEEN_POOL,
    daily_optimization_for_user,
    daily_optimization_from_breakdown,
    _pct,
)

# Legacy aliases (tests / docs may reference these names).
TEEN_LIFESTYLE_COMPLETION_MAX = {
    "nutrition": TEEN_NUTRITION_CAP,
    "lifestyle": TEEN_LIFESTYLE_MAX_POINTS,
    "habits": HABITS_COMPLETION_MAX,
}


def teen_combined_completion(user, log_date, subscription_data=None) -> dict:
    return daily_optimization_for_user(user, log_date, is_teen=True, subscription_data=subscription_data)


def adult_combined_completion(user, log_date, subscription_data=None) -> dict:
    return daily_optimization_for_user(user, log_date, is_teen=False, subscription_data=subscription_data)


def combined_completion_for_user(user, log_date, *, is_teen: bool, subscription_data=None) -> dict:
    return daily_optimization_for_user(
        user, log_date, is_teen=is_teen, subscription_data=subscription_data
    )


__all__ = [
    "ADULT_NUTRITION_COMPLETION_MAX",
    "ADULT_POOL",
    "HABITS_COMPLETION_MAX",
    "TEEN_LIFESTYLE_COMPLETION_MAX",
    "TEEN_LIFESTYLE_MAX_POINTS",
    "TEEN_POOL",
    "adult_combined_completion",
    "combined_completion_for_user",
    "daily_optimization_for_user",
    "daily_optimization_from_breakdown",
    "teen_combined_completion",
    "_pct",
]
