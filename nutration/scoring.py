"""Age-aware nutrition catalog scores (teen vs adult)."""

from __future__ import annotations

from utils.adult_nutrition import is_adult_flat_food_user
from utils.age import get_user_age


def module_food_score_for_user(module_food, user, age=None) -> int:
    """
    Return the catalog score for a ModuleFood row for this user.

    - Teen track: ``ModuleFood.score`` (legacy column, teen points).
    - Adult track: ``ModuleFood.adult_score`` (defaults to 1 for flat adult model).
    """
    if module_food is None:
        return 0
    if age is None:
        try:
            age = get_user_age(user)
        except Exception:
            age = 0
    if is_adult_flat_food_user(user, age):
        return int(getattr(module_food, "adult_score", None) or 1)
    return int(getattr(module_food, "score", None) or 0)
