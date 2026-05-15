"""
Adult (21+) PosturePlus nutrition (Engine 1) — flat model.

- Each qualifying food = 1 traceable point; each food_id at most once per local day.
- No 12 pt/day cap; practical max = unique foods in Disc + Muscle lists (13 in current catalog).
- Engine nutrition counts only when posture (workout) points > 0 that day (exercise gate).
- % bar: 0% if no disc/muscle food · 50% if at least one side but not both · 100% if ≥1 Disc and ≥1 Muscle.
"""

from __future__ import annotations

from collections.abc import Iterable

DISC_NAME_TOKENS = ("disc", "lubric", "spine")
MUSCLE_NAME_TOKENS = ("muscle", "repair", "fuel")

# Catalog size for UX copy / soft “complete list” hints (7 + 6 in spec).
ADULT_NUTRITION_FOOD_SLOT_MAX = 13


def adult_food_bucket(module) -> str | None:
    """
    Map a nutrition module to Disc vs Muscle adult buckets; None if not an adult bucket row.
    """
    if module is None:
        return None
    module_name = str(getattr(module, "name", "") or "").lower()
    module_cat = str(getattr(module, "nutrition_category", "") or "").lower()
    if module_cat == "disc" or any(t in module_name for t in DISC_NAME_TOKENS):
        return "disc"
    if module_cat == "muscle" or any(t in module_name for t in MUSCLE_NAME_TOKENS):
        return "muscle"
    return None


def adult_disc_muscle_food_id_sets(entries: Iterable) -> tuple[set[int], set[int]]:
    """Partition food entries into unique food_ids per bucket (``entries`` must have ``food_id`` set)."""
    disc_ids: set[int] = set()
    muscle_ids: set[int] = set()
    for n in entries:
        fid = getattr(n, "food_id", None)
        if not fid:
            continue
        mod = getattr(n, "module", None)
        b = adult_food_bucket(mod)
        if b == "disc":
            disc_ids.add(int(fid))
        elif b == "muscle":
            muscle_ids.add(int(fid))
    return disc_ids, muscle_ids


def adult_engine_nutrition_points(posture_pts: float, disc_ids: set[int], muscle_ids: set[int]) -> float:
    """Traceable engine nutrition points for adults (flat 1 per unique food per side)."""
    if posture_pts <= 0:
        return 0.0
    return float(len(disc_ids) + len(muscle_ids))


def adult_nutrition_bar_percent(disc_ids: set[int], muscle_ids: set[int]) -> int:
    """0 / 50 / 100 per redesigned adult nutrition bar."""
    if not disc_ids and not muscle_ids:
        return 0
    if disc_ids and muscle_ids:
        return 100
    return 50


def is_adult_flat_food_user(user, age) -> bool:
    """
    Adult PosturePlus flat food rules (once per food / day, toggle, 1 pt).
    Prefer account_tier so a mis-parsed age (0) does not route paid adults to teen behavior.
    """
    if getattr(user, "account_tier", None) == "adult":
        return True
    try:
        return int(age) >= 21
    except (TypeError, ValueError):
        return False


def toggle_adult_food_entry(session, *, module_id, food_id, servings="") -> bool:
    """
    Tap-to-toggle adult food log for one local day.

    Returns True if the food was un-logged, False if it was logged.
    """
    from nutration.models_log import NutraEntry

    food_id = int(food_id)
    removed, _ = NutraEntry.objects.filter(session=session, food_id=food_id).delete()
    if removed:
        return True
    NutraEntry.objects.create(
        session=session,
        module_id=int(module_id),
        food_id=food_id,
        servings=servings or "",
        score=1,
    )
    return False


def dedupe_adult_food_entries_for_session(session) -> None:
    """Keep a single NutraEntry per food_id within a session (newest wins)."""
    from nutration.models_log import NutraEntry

    for fid in (
        NutraEntry.objects.filter(session=session, food_id__isnull=False)
        .values_list("food_id", flat=True)
        .distinct()
    ):
        qs = NutraEntry.objects.filter(session=session, food_id=fid).order_by("-completed_at", "-id")
        pks = list(qs.values_list("pk", flat=True))
        if len(pks) > 1:
            NutraEntry.objects.filter(pk__in=pks[1:]).delete()
