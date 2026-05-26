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

ADULT_PLAN_MODULE_NAMES = (
    "Spine Support & Disc Lubrication Foods",
    "Posture Muscle Repair & Fuel Foods",
)

# Short titles used in admin / test seeds (must still appear on adult plan API).
ADULT_PLAN_MODULE_SHORT_NAMES = (
    "Disc Lubrication",
    "Posture Muscle Repair",
)


def adult_nutrition_plan_module_q():
    """
    Django Q for nutrition Module rows that belong on the adult food plan.
    Matches by nutrition_category and known module titles (not exact long names only).
    """
    from django.db.models import Q

    from nutration.models import Module

    nut = Module.NUTRITION
    q = Q(type=nut, nutrition_category__in=("disc", "muscle"))
    for name in ADULT_PLAN_MODULE_NAMES + ADULT_PLAN_MODULE_SHORT_NAMES:
        q |= Q(type=nut, name=name)
    return q

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


def adult_plan_module_buckets() -> dict[int, str]:
    """module_id -> disc|muscle for adult plan nutrition modules."""
    from django.core.cache import cache

    from nutration.models import Module

    cache_key = "nutration:adult_plan_module_buckets:v1"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    out: dict[int, str] = {}
    for m in Module.objects.filter(type="NUT").only("id", "name", "nutrition_category", "short_name"):
        b = adult_food_bucket(m)
        if b:
            out[int(m.id)] = b
    cache.set(cache_key, out, 3600)
    return out


def adult_catalog_food_bucket_map() -> dict[int, str]:
    """
    Map food_id -> disc|muscle from the adult nutrition catalog (ModuleFood on disc/muscle modules).
    Used when a log row references a teen UI module but the food is in the adult plan lists.
    """
    from django.db.models import Q

    from nutration.models import ModuleFood

    out: dict[int, str] = {}
    adult_name_to_bucket: dict[str, str] = {}

    def _register_food(mf, bucket: str) -> None:
        if not mf.food_id:
            return
        fid = int(mf.food_id)
        out.setdefault(fid, bucket)
        food = getattr(mf, "food", None)
        fname = str(getattr(food, "name", "") or "").strip().lower()
        if fname:
            adult_name_to_bucket.setdefault(fname, bucket)

    qs = ModuleFood.objects.filter(
        Q(module__nutrition_category__in=("disc", "muscle"))
        | Q(module__name__in=ADULT_PLAN_MODULE_NAMES)
    ).select_related("module", "food")
    for mf in qs:
        b = adult_food_bucket(mf.module)
        if b:
            _register_food(mf, b)

    # Foods logged under teen modules often share the same Food rows as the adult plan lists.
    teen_qs = ModuleFood.objects.filter(module__nutrition_category="teen").select_related("food")
    for mf in teen_qs:
        if not mf.food_id:
            continue
        fid = int(mf.food_id)
        if fid in out:
            continue
        food = getattr(mf, "food", None)
        fname = str(getattr(food, "name", "") or "").strip().lower()
        if fname and fname in adult_name_to_bucket:
            out[fid] = adult_name_to_bucket[fname]

    return out


def adult_disc_muscle_food_id_sets(entries: Iterable) -> tuple[set[int], set[int]]:
    """Partition food entries into unique food_ids per disc/muscle bucket."""
    catalog = adult_catalog_food_bucket_map()
    plan_modules = adult_plan_module_buckets()
    disc_ids: set[int] = set()
    muscle_ids: set[int] = set()
    for n in entries:
        fid = getattr(n, "food_id", None)
        if not fid:
            continue
        fid = int(fid)
        mod = getattr(n, "module", None)
        mid = int(getattr(mod, "id", 0) or 0)
        b = plan_modules.get(mid) or adult_food_bucket(mod) or catalog.get(fid)
        if b == "disc":
            disc_ids.add(fid)
        elif b == "muscle":
            muscle_ids.add(fid)
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
    Uses account_tier when set; otherwise sex-specific adult age band (female 18+, male 21+).
    """
    from utils.age import get_user_age_exact
    from utils.paywall_flags import is_adult_age

    if getattr(user, "account_tier", None) == "adult":
        return True
    if getattr(user, "account_tier", None) == "teen":
        return False
    return is_adult_age(get_user_age_exact(user), age, user=user)


def toggle_adult_food_entry(session, *, module_id, food_id, servings="", score=1) -> bool:
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
        score=max(1, int(score or 1)),
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
