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
ADULT_WATER_ML_PER_UNIT = 500  # legacy alias
ADULT_TIER1_POINTS_EACH = 2
ADULT_TIER2_POINTS_EACH = 1

# Monday F4 — Tier 1 spine drinks (+2 pts per serving).
ADULT_TIER1_ITEMS = [
    {"key": "bone_broth", "label": "Bone Broth"},
    {"key": "watermelon", "label": "Watermelon"},
    {"key": "coconut", "label": "Coconut"},
    {"key": "cucumber", "label": "Cucumber"},
    {"key": "celery", "label": "Celery"},
    {"key": "beet", "label": "Beet"},
]
ADULT_TIER1_KEYS = {d["key"] for d in ADULT_TIER1_ITEMS}

# Monday F4 — Tier 2 baseline liquids (+1 pt per serving).
ADULT_TIER2_ITEMS = [
    {"key": "water", "label": "Water"},
    {"key": "milk", "label": "Milk"},
    {"key": "tea", "label": "Tea"},
    {"key": "coffee", "label": "Coffee"},
    {"key": "juice", "label": "Juice"},
    {"key": "carbonated", "label": "Carbonated"},
]
ADULT_TIER2_KEYS = {d["key"] for d in ADULT_TIER2_ITEMS}

# Legacy spine drink keys (alias → tier1 key).
ADULT_SPINE_DRINK_LEGACY_ALIASES = {
    "bone_broth": "bone_broth",
    "watermelon_juice": "watermelon",
    "watermelon": "watermelon",
    "coconut_water": "coconut",
    "coconut": "coconut",
    "cucumber_juice": "cucumber",
    "cucumber": "cucumber",
    "celery_juice": "celery",
    "celery": "celery",
    "beet_juice": "beet",
    "beet": "beet",
}

# §2.2 quick-add protein chips (UI hints only — logging is grams-only per Monday F2).
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

# Backward-compat aliases for older clients.
ADULT_SPINE_DRINK_TYPES = ADULT_TIER1_ITEMS
ADULT_SPINE_DRINK_KEYS = ADULT_TIER1_KEYS | set(ADULT_SPINE_DRINK_LEGACY_ALIASES.keys())


def _coerce_tier_log(raw, valid_keys: set[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            key = str(k or "").strip().lower()
            if key in valid_keys:
                out[key] = max(0, int(v or 0))
    return out


def normalize_tier1_key(key: str) -> str | None:
    k = str(key or "").strip().lower()
    if k in ADULT_TIER1_KEYS:
        return k
    return ADULT_SPINE_DRINK_LEGACY_ALIASES.get(k)


def tier1_log_from_row(row) -> dict[str, int]:
    if row is None:
        return {}
    tier1 = _coerce_tier_log(getattr(row, "tier1_log", None) or {}, ADULT_TIER1_KEYS)
    if tier1:
        return tier1
    # Legacy spine_drinks list.
    for drink in list(getattr(row, "spine_drinks", None) or []):
        mapped = normalize_tier1_key(drink.get("type"))
        if mapped:
            tier1[mapped] = tier1.get(mapped, 0) + int(drink.get("count", 0) or 0)
    if not tier1 and int(getattr(row, "spine_500ml_count", 0) or 0) > 0:
        tier1["bone_broth"] = int(row.spine_500ml_count)
    return tier1


def tier2_log_from_row(row) -> dict[str, int]:
    if row is None:
        return {}
    tier2 = _coerce_tier_log(getattr(row, "tier2_log", None) or {}, ADULT_TIER2_KEYS)
    if tier2:
        return tier2
    water_units = max(0, int(getattr(row, "water_ml", 0) or 0)) // ADULT_WATER_ML_PER_UNIT
    if water_units:
        tier2["water"] = water_units
    return tier2


def tier_log_total(log: dict[str, int]) -> int:
    return sum(max(0, int(v or 0)) for v in (log or {}).values())


def adult_fluid_points_raw(tier1_log: dict[str, int], tier2_log: dict[str, int]) -> int:
    """Uncapped fluid points from tier counts (Monday F1)."""
    t1 = tier_log_total(tier1_log)
    t2 = tier_log_total(tier2_log)
    return (t1 * ADULT_TIER1_POINTS_EACH) + (t2 * ADULT_TIER2_POINTS_EACH)


def adult_fluid_points(tier1_log: dict[str, int], tier2_log: dict[str, int]) -> int:
    return min(ADULT_HYDRATION_POINTS_CAP, adult_fluid_points_raw(tier1_log, tier2_log))


def sync_legacy_hydration_fields(row) -> None:
    """Keep deprecated water_ml / spine_* fields aligned with tier logs."""
    tier1 = tier1_log_from_row(row)
    tier2 = tier2_log_from_row(row)
    row.tier1_log = tier1
    row.tier2_log = tier2
    row.spine_500ml_count = tier_log_total(tier1)
    row.water_ml = int(tier2.get("water", 0)) * ADULT_WATER_ML_PER_UNIT
    row.spine_drinks = [{"type": k, "count": v} for k, v in sorted(tier1.items()) if v > 0]


def adult_protein_points(protein_grams: int) -> int:
    """§2.1: 1 pt per 10 g protein, capped at 9 (90 g)."""
    grams = max(0, int(protein_grams or 0))
    return min(ADULT_PROTEIN_POINTS_CAP, grams // ADULT_PROTEIN_GRAMS_PER_POINT)


def adult_hydration_points(water_ml: int, spine_500ml_count: int) -> int:
    """Legacy wrapper — prefer adult_fluid_points(tier1, tier2)."""
    tier2: dict[str, int] = {}
    water_units = max(0, int(water_ml or 0)) // ADULT_WATER_ML_PER_UNIT
    if water_units:
        tier2["water"] = water_units
    tier1: dict[str, int] = {}
    spine_units = max(0, int(spine_500ml_count or 0))
    if spine_units:
        tier1["bone_broth"] = spine_units
    return adult_fluid_points(tier1, tier2)


def adult_nutrition_points_from_logs(
    protein_grams: int,
    tier1_log: dict[str, int],
    tier2_log: dict[str, int],
) -> int:
    return min(
        ADULT_NUTRITION_POINTS_CAP,
        adult_protein_points(protein_grams) + adult_fluid_points(tier1_log, tier2_log),
    )


def adult_nutrition_points(protein_grams: int, water_ml: int, spine_500ml_count: int) -> int:
    """Legacy signature — maps water/spine totals into tier-style scoring."""
    tier2 = {}
    water_units = max(0, int(water_ml or 0)) // ADULT_WATER_ML_PER_UNIT
    if water_units:
        tier2["water"] = water_units
    tier1 = {}
    spine_units = max(0, int(spine_500ml_count or 0))
    if spine_units:
        tier1["bone_broth"] = spine_units
    return adult_nutrition_points_from_logs(protein_grams, tier1, tier2)


def get_adult_nutrition_day(user, log_date):
    """Fetch (without creating) the AdultNutritionDay row for a user/day, or None."""
    from nutration.models_log import AdultNutritionDay

    return AdultNutritionDay.objects.filter(user=user, log_date=log_date).first()


def build_hydration_log_entries(
    water_ml: int,
    spine_drinks: list | None = None,
) -> list[dict]:
    """
    Expand stored totals into one UI row per 500 ml tap.

    Example: water_ml=3000 → six entries labelled "500 ml".
    Spine drinks expand per type (each serving is 500 ml).
    """
    spine_label_map = {d["key"]: d["label"] for d in ADULT_SPINE_DRINK_TYPES}
    entries: list[dict] = []
    water_units = max(0, int(water_ml or 0)) // ADULT_WATER_ML_PER_UNIT
    for _ in range(water_units):
        entries.append(
            {
                "type": "water",
                "ml": ADULT_WATER_ML_PER_UNIT,
                "label": f"{ADULT_WATER_ML_PER_UNIT} ml",
            }
        )
    for drink in list(spine_drinks or []):
        dtype = str(drink.get("type") or "").strip().lower()
        count = max(0, int(drink.get("count", 0) or 0))
        drink_label = spine_label_map.get(dtype, dtype.replace("_", " ").title())
        for _ in range(count):
            entries.append(
                {
                    "type": "spine_drink",
                    "ml": ADULT_WATER_ML_PER_UNIT,
                    "label": f"{drink_label} {ADULT_WATER_ML_PER_UNIT} ml",
                    "drink_type": dtype,
                }
            )
    return entries


def adult_nutrition_points_today(user, log_date) -> int:
    """Server-authoritative adult nutrition points for the day (0..15)."""
    row = get_adult_nutrition_day(user, log_date)
    if not row:
        return 0
    return adult_nutrition_points_from_logs(
        row.protein_grams,
        tier1_log_from_row(row),
        tier2_log_from_row(row),
    )


def _tier_items_payload(catalog: list[dict], log: dict[str, int], points_each: int) -> list[dict]:
    return [
        {
            "key": item["key"],
            "label": item["label"],
            "count": int(log.get(item["key"], 0) or 0),
            "points_each": points_each,
        }
        for item in catalog
    ]


def adult_nutrition_state(user, log_date) -> dict:
    """Full server-authoritative state for the adult nutrition screen / API."""
    row = get_adult_nutrition_day(user, log_date)
    protein_grams = int(getattr(row, "protein_grams", 0) or 0)
    tier1 = tier1_log_from_row(row)
    tier2 = tier2_log_from_row(row)

    p_pts = adult_protein_points(protein_grams)
    fluid_raw = adult_fluid_points_raw(tier1, tier2)
    f_pts = adult_fluid_points(tier1, tier2)
    n_pts = min(ADULT_NUTRITION_POINTS_CAP, p_pts + f_pts)
    return {
        "log_date": str(log_date),
        "protein": {
            "grams": protein_grams,
            "points": p_pts,
            "grams_cap": ADULT_PROTEIN_GRAMS_CAP,
            "points_cap": ADULT_PROTEIN_POINTS_CAP,
            "gram_buttons": [10, 20, 30],
        },
        "tier1": {
            "items": _tier_items_payload(ADULT_TIER1_ITEMS, tier1, ADULT_TIER1_POINTS_EACH),
            "log": tier1,
            "points_raw": min(ADULT_HYDRATION_POINTS_CAP, tier_log_total(tier1) * ADULT_TIER1_POINTS_EACH),
            "points_each": ADULT_TIER1_POINTS_EACH,
        },
        "tier2": {
            "items": _tier_items_payload(ADULT_TIER2_ITEMS, tier2, ADULT_TIER2_POINTS_EACH),
            "log": tier2,
            "points_raw": min(
                ADULT_HYDRATION_POINTS_CAP,
                tier_log_total(tier2) * ADULT_TIER2_POINTS_EACH,
            ),
            "points_each": ADULT_TIER2_POINTS_EACH,
        },
        "fluids": {
            "points": f_pts,
            "points_cap": ADULT_HYDRATION_POINTS_CAP,
            "points_raw": fluid_raw,
            "label": f"Fluids {f_pts} / {ADULT_HYDRATION_POINTS_CAP} pts",
        },
        # Legacy block for clients not yet on tier UI.
        "hydration": {
            "water_ml": int(tier2.get("water", 0)) * ADULT_WATER_ML_PER_UNIT,
            "water_500ml_units": int(tier2.get("water", 0) or 0),
            "spine_500ml_count": tier_log_total(tier1),
            "spine_drinks": [{"type": k, "count": v} for k, v in tier1.items() if v > 0],
            "points": f_pts,
            "points_cap": ADULT_HYDRATION_POINTS_CAP,
            "spine_drink_types": ADULT_TIER1_ITEMS,
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
