"""Monday F — adult nutrition API (protein + tier1/tier2 fluids).

GET  /api/adult-nutrition          -> today's server-authoritative state
POST /api/adult-nutrition          -> apply an action, returns updated state

Actions (field ``action``):
  add_protein / set_protein / undo_protein   — protein grams only
  add_tier1 / undo_tier1                     — {item: bone_broth|watermelon|...}
  add_tier2 / undo_tier2                     — {item: water|milk|tea|...}
  add_spine_drink / undo_spine_drink         — legacy alias for tier1
  add_water / undo_water                     — legacy alias for tier2 water
  reset                                      — clear the day
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from nutration.models_log import AdultNutritionDay
from utils.adult_nutrition import (
    ADULT_PROTEIN_CHIPS,
    ADULT_TIER1_KEYS,
    ADULT_TIER2_KEYS,
    ADULT_WATER_ML_PER_UNIT,
    adult_nutrition_state,
    is_adult_flat_food_user,
    normalize_tier1_key,
    sync_legacy_hydration_fields,
    tier1_log_from_row,
    tier2_log_from_row,
)
from utils.age import get_user_age_exact
from utils.monetization_gate import logging_locked_payload
from utils.user_time import user_today

_CHIP_GRAMS = {c["key"]: int(c["grams"]) for c in ADULT_PROTEIN_CHIPS}


def _is_adult(user) -> bool:
    try:
        age = get_user_age_exact(user)
        return is_adult_flat_food_user(user, age)
    except Exception:
        return getattr(user, "account_tier", None) == "adult"


def _apply_tier_delta(row: AdultNutritionDay, tier: str, item: str, delta: int) -> None:
    if tier == "tier1":
        key = normalize_tier1_key(item)
        valid = ADULT_TIER1_KEYS
    else:
        key = str(item or "").strip().lower()
        valid = ADULT_TIER2_KEYS
    if not key or key not in valid:
        raise ValueError(f"item must be one of {sorted(valid)}.")

    if tier == "tier1":
        log = tier1_log_from_row(row)
        log[key] = max(0, int(log.get(key, 0)) + delta)
        row.tier1_log = {k: v for k, v in log.items() if v > 0}
    else:
        log = tier2_log_from_row(row)
        log[key] = max(0, int(log.get(key, 0)) + delta)
        row.tier2_log = {k: v for k, v in log.items() if v > 0}
    sync_legacy_hydration_fields(row)


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
        locked = logging_locked_payload(
            user,
            detail="Nutrition logging is locked. Subscribe to unlock full access.",
        )
        if locked:
            return Response(locked, status=status.HTTP_403_FORBIDDEN)

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

        item = str(data.get("item") or data.get("drink_type") or "").strip().lower()

        try:
            if action in ("add_protein", "add_protein_chip"):
                chip = str(data.get("chip", "") or "").strip()
                grams = _CHIP_GRAMS.get(chip, 0) if chip else _int("grams")
                if grams <= 0:
                    return Response(
                        {"detail": "grams is required."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                row.protein_grams = max(0, int(row.protein_grams) + grams)
            elif action == "set_protein":
                row.protein_grams = _int("grams")
            elif action == "undo_protein":
                grams = _int("grams") or 10
                row.protein_grams = max(0, int(row.protein_grams) - grams)
            elif action in ("add_tier1", "undo_tier1", "add_spine_drink", "undo_spine_drink"):
                if not item:
                    return Response({"detail": "item (or drink_type) is required."}, status=400)
                delta = 1 if action in ("add_tier1", "add_spine_drink") else -1
                _apply_tier_delta(row, "tier1", item, delta)
            elif action in ("add_tier2", "undo_tier2"):
                if not item:
                    return Response({"detail": "item is required."}, status=400)
                delta = 1 if action == "add_tier2" else -1
                _apply_tier_delta(row, "tier2", item, delta)
            elif action == "add_water":
                _apply_tier_delta(row, "tier2", "water", 1)
            elif action == "undo_water":
                _apply_tier_delta(row, "tier2", "water", -1)
            elif action == "reset":
                row.protein_grams = 0
                row.water_ml = 0
                row.spine_500ml_count = 0
                row.spine_drinks = []
                row.tier1_log = {}
                row.tier2_log = {}
            else:
                return Response({"detail": f"Unknown action: {action!r}"}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        row.save()

        try:
            from users.spec_runtime import compute_daily_height_for_user

            compute_daily_height_for_user(user, log_date, force_recompute=True)
        except Exception:
            pass

        return Response(adult_nutrition_state(user, log_date), status=status.HTTP_200_OK)
