"""Part 2 — adult nutrition redesign API (protein + hydration).

GET  /api/nutrition/adult-nutrition          -> today's server-authoritative state
POST /api/nutrition/adult-nutrition          -> apply an action, returns updated state

Actions (field ``action``):
  add_protein        {grams}                add protein grams (chips use this)
  set_protein        {grams}                set protein grams
  undo_protein       {grams}                subtract protein grams (floored at 0)
  add_water          {ml=500}               add water millilitres
  undo_water         {ml=500}               subtract water millilitres
  add_spine_drink    {drink_type}           +1 spine 500 ml serving of a type
  undo_spine_drink   {drink_type}           -1 spine serving of a type
  reset                                     clear the day
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nutration.models_log import AdultNutritionDay
from utils.adult_nutrition import (
    ADULT_PROTEIN_CHIPS,
    ADULT_SPINE_DRINK_KEYS,
    ADULT_WATER_ML_PER_UNIT,
    adult_nutrition_state,
    is_adult_flat_food_user,
)
from utils.age import get_user_age_exact
from utils.user_time import user_today

_CHIP_GRAMS = {c["key"]: int(c["grams"]) for c in ADULT_PROTEIN_CHIPS}


def _is_adult(user) -> bool:
    try:
        age = get_user_age_exact(user)
        return is_adult_flat_food_user(user, age)
    except Exception:
        return getattr(user, "account_tier", None) == "adult"


def _apply_spine_delta(row: AdultNutritionDay, drink_type: str, delta: int) -> None:
    """Adjust the per-type spine-drink breakdown and the 500 ml count together."""
    drinks = {d.get("type"): int(d.get("count", 0)) for d in (row.spine_drinks or [])}
    drinks[drink_type] = max(0, drinks.get(drink_type, 0) + delta)
    row.spine_drinks = [{"type": k, "count": v} for k, v in drinks.items() if v > 0]
    row.spine_500ml_count = max(0, sum(v for v in drinks.values()))


class AdultNutritionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not _is_adult(user):
            return Response(
                {"detail": "Adult nutrition is available for adult accounts only."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(adult_nutrition_state(user, user_today(user)), status=status.HTTP_200_OK)

    def post(self, request):
        user = request.user
        if not _is_adult(user):
            return Response(
                {"detail": "Adult nutrition is available for adult accounts only."},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = request.data or {}
        action = str(data.get("action", "") or "").strip().lower()
        log_date = user_today(user)
        row, _ = AdultNutritionDay.objects.get_or_create(user=user, log_date=log_date)

        def _int(key, default=0):
            try:
                return max(0, int(data.get(key, default) or 0))
            except (TypeError, ValueError):
                return default

        if action in ("add_protein", "add_protein_chip"):
            chip = str(data.get("chip", "") or "").strip()
            grams = _CHIP_GRAMS.get(chip, 0) if chip else _int("grams")
            if grams <= 0:
                return Response({"detail": "grams (or a valid chip) is required."}, status=status.HTTP_400_BAD_REQUEST)
            row.protein_grams = max(0, int(row.protein_grams) + grams)
        elif action == "set_protein":
            row.protein_grams = _int("grams")
        elif action == "undo_protein":
            grams = _int("grams")
            row.protein_grams = max(0, int(row.protein_grams) - grams)
        elif action == "add_water":
            ml = _int("ml", ADULT_WATER_ML_PER_UNIT) or ADULT_WATER_ML_PER_UNIT
            row.water_ml = max(0, int(row.water_ml) + ml)
        elif action == "undo_water":
            ml = _int("ml", ADULT_WATER_ML_PER_UNIT) or ADULT_WATER_ML_PER_UNIT
            row.water_ml = max(0, int(row.water_ml) - ml)
        elif action in ("add_spine_drink", "undo_spine_drink"):
            drink_type = str(data.get("drink_type", "") or "").strip().lower()
            if drink_type not in ADULT_SPINE_DRINK_KEYS:
                return Response(
                    {"detail": f"drink_type must be one of {sorted(ADULT_SPINE_DRINK_KEYS)}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            _apply_spine_delta(row, drink_type, 1 if action == "add_spine_drink" else -1)
        elif action == "reset":
            row.protein_grams = 0
            row.water_ml = 0
            row.spine_500ml_count = 0
            row.spine_drinks = []
        else:
            return Response({"detail": f"Unknown action: {action!r}"}, status=status.HTTP_400_BAD_REQUEST)

        row.save()

        # Recompute the user's height/ledger so the new nutrition points apply immediately.
        try:
            from users.spec_runtime import compute_daily_height_for_user

            compute_daily_height_for_user(user, log_date, force_recompute=True)
        except Exception:
            pass

        return Response(adult_nutrition_state(user, log_date), status=status.HTTP_200_OK)
