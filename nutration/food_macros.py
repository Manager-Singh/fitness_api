"""Food macro totals and hydration summary for nutrition plan / log APIs."""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from nutration.models_log import NutraEntry


def _food_calories(food) -> int:
    return int(food.calories or 0) if food and food.calories is not None else 0


def _food_protein(food) -> float:
    if not food or food.protein is None:
        return 0.0
    return float(food.protein)


def food_macros_from_entries(entries: Iterable[NutraEntry]) -> dict:
    """Sum calories and protein from logged food entries (null-safe)."""
    total_calories = 0
    total_protein = Decimal("0")
    for entry in entries:
        if not entry.food_id:
            continue
        food = entry.food
        total_calories += _food_calories(food)
        total_protein += Decimal(str(_food_protein(food)))
    return {
        "today_total_calories": total_calories,
        "today_total_protein": float(total_protein),
    }


def food_log_item_macros(food) -> dict:
    return {
        "calories": _food_calories(food),
        "protein": _food_protein(food),
    }


def hydration_summary_for_user(user, log_date, *, adult_nutrition_plan: bool) -> dict:
    """
    Server-authoritative hydration consumed today.
    Adults: ml from AdultNutritionDay (water + spine drinks).
    Teens: lifestyle hydration channel (points-based; no ml tracking).
    """
    if adult_nutrition_plan:
        from utils.adult_nutrition import ADULT_WATER_ML_PER_UNIT, get_adult_nutrition_day

        from utils.adult_nutrition import build_hydration_log_entries

        row = get_adult_nutrition_day(user, log_date)
        water_ml = int(getattr(row, "water_ml", 0) or 0)
        spine_count = int(getattr(row, "spine_500ml_count", 0) or 0)
        spine_drinks = list(getattr(row, "spine_drinks", []) or [])
        spine_ml = spine_count * ADULT_WATER_ML_PER_UNIT
        total_ml = water_ml + spine_ml
        logs = build_hydration_log_entries(water_ml, spine_drinks)
        return {
            "tracking": "ml",
            "water_ml": water_ml,
            "water_500ml_units": water_ml // ADULT_WATER_ML_PER_UNIT,
            "spine_500ml_count": spine_count,
            "spine_ml": spine_ml,
            "total_ml": total_ml,
            "total_liters": round(total_ml / 1000.0, 2),
            "spine_drinks": spine_drinks,
            "logs": logs,
            "today_logged_hydration": [e["label"] for e in logs],
        }

    from utils.teen_dashboard_dots import teen_lifestyle_channel_scores

    channels = teen_lifestyle_channel_scores(user, log_date)
    hyd_pts = float(channels.get("hyd") or 0)
    return {
        "tracking": "lifestyle",
        "logged": hyd_pts > 0,
        "points": hyd_pts,
        "goal_points": 1,
    }
