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


def adult_lifestyle_plan_module_pks() -> set[int]:
    """
    Lifestyle (LIFE) modules for paid adult plans (male 21+ / female 18+).

    Lifestyle rows are often seeded on teen age groups (e.g. 13–20) so strict
    per-user age filtering leaves male adults with an empty lifestyle list.
  """
    from nutration.models import Module

    return set(
        Module.objects.filter(type=Module.LIFESTYLE).values_list("pk", flat=True)
    )

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
    """Traceable engine nutrition points for adults (flat 1 per unique food per side).

    DEPRECATED (Part 2): retained only for legacy/back-compat. The adult engine now uses
    the protein+hydration model (adult_nutrition_points_today). Kept so old data and
    tooling don't break during the transition.
    """
    if posture_pts <= 0:
        return 0.0
    return float(len(disc_ids) + len(muscle_ids))


# ===========================================================================
# Part 2 — adult nutrition redesign (protein + hydration). Server-authoritative.
# ===========================================================================

ADULT_PROTEIN_POINTS_CAP = 9
ADULT_HYDRATION_POINTS_CAP = 6
ADULT_NUTRITION_POINTS_CAP = 15
ADULT_PROTEIN_GRAMS_PER_POINT = 10
ADULT_PROTEIN_GRAMS_CAP = 90  # 9 pts
ADULT_WATER_ML_PER_UNIT = 500  # 1 pt per 500 ml
ADULT_SPINE_POINTS_PER_UNIT = 2  # 2 pts per 500 ml spine drink

# §2.2 quick-add protein chips (one tap = add grams, no math).
ADULT_PROTEIN_CHIPS = [
    {"key": "chicken_breast", "label": "Chicken breast", "grams": 30},
    {"key": "steak", "label": "Steak", "grams": 26},
    {"key": "two_eggs", "label": "2 Eggs", "grams": 12},
    {"key": "beans_lentils", "label": "Beans/lentils", "grams": 18},
    {"key": "greek_yogurt", "label": "Greek yogurt", "grams": 17},
    {"key": "tofu", "label": "Tofu", "grams": 17},
    {"key": "whey_scoop", "label": "Whey scoop", "grams": 24},
    {"key": "salmon", "label": "Salmon", "grams": 25},
]

# §2.3 the six spine drinks (all support discs / connective tissue), worth 2 pts / 500 ml.
ADULT_SPINE_DRINK_TYPES = [
    {"key": "bone_broth", "label": "Bone Broth"},
    {"key": "watermelon_juice", "label": "Watermelon Juice"},
    {"key": "coconut_water", "label": "Coconut Water"},
    {"key": "cucumber_juice", "label": "Cucumber Juice"},
    {"key": "celery_juice", "label": "Celery Juice"},
    {"key": "beet_juice", "label": "Beet Juice"},
]
ADULT_SPINE_DRINK_KEYS = {d["key"] for d in ADULT_SPINE_DRINK_TYPES}


def adult_protein_points(protein_grams: int) -> int:
    """§2.1: 1 pt per 10 g protein, capped at 9 (90 g)."""
    grams = max(0, int(protein_grams or 0))
    return min(ADULT_PROTEIN_POINTS_CAP, grams // ADULT_PROTEIN_GRAMS_PER_POINT)


def adult_hydration_points(water_ml: int, spine_500ml_count: int) -> int:
    """§2.1: water 1 pt/500 ml + spine drink 2 pts/500 ml, capped at 6."""
    water_units = max(0, int(water_ml or 0)) // ADULT_WATER_ML_PER_UNIT
    spine_units = max(0, int(spine_500ml_count or 0))
    raw = (water_units * 1) + (spine_units * ADULT_SPINE_POINTS_PER_UNIT)
    return min(ADULT_HYDRATION_POINTS_CAP, raw)


def adult_nutrition_points(protein_grams: int, water_ml: int, spine_500ml_count: int) -> int:
    """§2.1: nutrition_points = min(15, protein_points + hydration_points)."""
    return min(
        ADULT_NUTRITION_POINTS_CAP,
        adult_protein_points(protein_grams) + adult_hydration_points(water_ml, spine_500ml_count),
    )


def get_adult_nutrition_day(user, log_date):
    """Fetch (without creating) the AdultNutritionDay row for a user/day, or None."""
    from nutration.models_log import AdultNutritionDay

    return AdultNutritionDay.objects.filter(user=user, log_date=log_date).first()


def adult_nutrition_points_today(user, log_date) -> int:
    """Server-authoritative adult nutrition points for the day (0..15)."""
    row = get_adult_nutrition_day(user, log_date)
    if not row:
        return 0
    return adult_nutrition_points(row.protein_grams, row.water_ml, row.spine_500ml_count)


def adult_nutrition_state(user, log_date) -> dict:
    """Full server-authoritative state for the adult nutrition screen / API."""
    row = get_adult_nutrition_day(user, log_date)
    protein_grams = int(getattr(row, "protein_grams", 0) or 0)
    water_ml = int(getattr(row, "water_ml", 0) or 0)
    spine_500ml = int(getattr(row, "spine_500ml_count", 0) or 0)
    spine_drinks = list(getattr(row, "spine_drinks", []) or [])

    p_pts = adult_protein_points(protein_grams)
    h_pts = adult_hydration_points(water_ml, spine_500ml)
    n_pts = min(ADULT_NUTRITION_POINTS_CAP, p_pts + h_pts)
    return {
        "log_date": str(log_date),
        "protein": {
            "grams": protein_grams,
            "points": p_pts,
            "grams_cap": ADULT_PROTEIN_GRAMS_CAP,
            "points_cap": ADULT_PROTEIN_POINTS_CAP,
            "chips": ADULT_PROTEIN_CHIPS,
        },
        "hydration": {
            "water_ml": water_ml,
            "water_500ml_units": water_ml // ADULT_WATER_ML_PER_UNIT,
            "spine_500ml_count": spine_500ml,
            "spine_drinks": spine_drinks,
            "points": h_pts,
            "points_cap": ADULT_HYDRATION_POINTS_CAP,
            "spine_drink_types": ADULT_SPINE_DRINK_TYPES,
        },
        "nutrition_points": n_pts,
        "nutrition_points_cap": ADULT_NUTRITION_POINTS_CAP,
        "engine": "engine1",
        "cm_per_point": 0.001,
    }


def adult_nutrition_bar_percent(disc_ids: set[int], muscle_ids: set[int]) -> int:
    """0 / 50 / 100 per redesigned adult nutrition bar."""
    if not disc_ids and not muscle_ids:
        return 0
    if disc_ids and muscle_ids:
        return 100
    return 50


def adult_food_completion_percent_legacy(user, log_date) -> int:
    """
    Legacy disc/muscle food-list completion (0 / 50 / 100) for adults who still log
    nutrition through the old food-toggle UI (NutraEntry) instead of the Part 2
    protein+hydration endpoint. Used as a fallback so already-logged food still counts
    toward dashboard completion until the client migrates to /adult-nutrition.
    """
    from nutration.models_log import NutraEntry

    entries = NutraEntry.objects.filter(
        session__user=user, session__date=log_date, food__isnull=False
    ).select_related("module")
    disc_ids, muscle_ids = adult_disc_muscle_food_id_sets(entries)
    return adult_nutrition_bar_percent(disc_ids, muscle_ids)


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
