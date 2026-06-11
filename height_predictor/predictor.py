"""
Ultimate Height Predictor — Model v2 (the 20-point prediction engine).

This is a SELF-CONTAINED, side-effect-free transcription of HeightApp_Ultimate_Predictor_Spec
(Parts 5-7 and the Part 9 pseudocode). It does NOT read the database, does NOT touch the daily
points / Engine 1 / Engine 2 / ledger / dashboard, and does NOT recompute posture. Posture
recovery is passed in by the caller (read from the existing PostureState).

Output: one number in cm (`true_optimized_cm`) plus a breakdown for transparency.

True_Optimized_Height = Genetic_Potential + Posture_Recovery
  Genetic_Potential = blend(current-height-driven maturity estimate, mid-parent height)
  Posture_Recovery  = the already-computed recoverable cm (passed in, never re-derived)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

MODEL_VERSION = "v2"

# Age-band thresholds (decimal years).
BAND_A_MAX_EXCLUSIVE = 17.5   # 13.0 .. 17.49  -> full model
BAND_B_MAX_INCLUSIVE = 20.0   # 17.5 .. 20.0   -> lite model
# 20+ -> posture-only fallback.

# Biological-age table bounds (Part 5 STEP 3 / Part 7).
BIO_AGE_MIN = 12.0
BIO_AGE_MAX = 20.0

# --- Tunable constants (Part 9 calibration plan). Named so they can be re-fit later. ---
MATURITY_FACTOR = 0.25            # delta(maturity) -> years of bio-age offset
MATURITY_OFFSET_CLAMP = 2.0       # +/- years
VELOCITY_FACTOR = 0.10            # cm/yr delta -> years of bio-age nudge
VELOCITY_CLAMP = 0.7              # +/- years
W_MATURITY_BASE = 0.55            # blend weight at age 13
W_MATURITY_SLOPE = 0.055          # blend weight increase per year of age
W_MATURITY_MIN = 0.55
W_MATURITY_MAX = 0.95
MPH_SEX_ADJUST_CM = 13.0          # +13 male / -13 female

# Frame (wrist) refinement (Part 5 STEP 8).
FRAME_LARGE_RATIO = 10.0
FRAME_SMALL_RATIO = 11.5
FRAME_LARGE_ADJ = 0.8
FRAME_SMALL_ADJ = -0.5

# Wingspan / ape-index refinement (Part 5 STEP 8) — deliberately tiny + optional.
APE_INDEX_THRESHOLD = 6.0
WING_ADJ = 0.7

# Fraction-of-adult-height tables (Part 7). Kept inside the predictor for isolation.
# Values match the CDC-median-derived fractions in the spec. Interpolate linearly; bound
# biological_age to [12.0, 20.0].
FRACTION_ATTAINED_MALE = {
    12.0: 0.847, 12.5: 0.867, 13.0: 0.889, 13.5: 0.906, 14.0: 0.923, 14.5: 0.938,
    15.0: 0.955, 15.5: 0.966, 16.0: 0.977, 16.5: 0.986, 17.0: 0.991, 17.5: 0.994,
    18.0: 0.997, 18.5: 0.999, 19.0: 1.000, 20.0: 1.000,
}
FRACTION_ATTAINED_FEMALE = {
    12.0: 0.929, 12.5: 0.945, 13.0: 0.960, 13.5: 0.969, 14.0: 0.979, 14.5: 0.985,
    15.0: 0.991, 15.5: 0.994, 16.0: 0.997, 16.5: 0.999, 17.0: 1.000, 17.5: 1.000,
    18.0: 1.000, 20.0: 1.000,
}

# Expected maturity by age (Part 5 STEP 3). Girls mature ~2 years earlier.
EXPECTED_MATURITY_MALE = {12.0: 1.0, 13.0: 2.0, 14.0: 4.0, 15.0: 6.0, 16.0: 7.5, 17.0: 9.0, 18.0: 10.0}
EXPECTED_MATURITY_FEMALE = {11.0: 2.0, 12.0: 4.0, 13.0: 6.0, 14.0: 8.0, 15.0: 9.0, 16.0: 10.0}

# Expected growth velocity cm/year (Part 5 STEP 4).
EXPECTED_GROWTH_MALE = {13.0: 7.0, 14.0: 8.0, 15.0: 6.0, 16.0: 3.5, 17.0: 1.5, 18.0: 0.5}
EXPECTED_GROWTH_FEMALE = {13.0: 5.0, 14.0: 3.0, 15.0: 1.5, 16.0: 0.7, 17.0: 0.3}

# Female menarche_status (0/1/2/3) -> maturity points (Part 5 STEP 2).
MENARCHE_POINTS = [0.0, 5.0, 8.0, 10.0]


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _is_male(sex: Optional[str]) -> bool:
    return str(sex or "").strip().lower() == "male"


def _interp_table(table: dict, x: float) -> float:
    """Linear interpolation over a {age: value} table, clamped to the table's range."""
    keys = sorted(table.keys())
    if x <= keys[0]:
        return table[keys[0]]
    if x >= keys[-1]:
        return table[keys[-1]]
    lo = keys[0]
    for k in keys:
        if k <= x:
            lo = k
        else:
            hi = k
            frac = (x - lo) / (hi - lo)
            return table[lo] + (table[hi] - table[lo]) * frac
    return table[keys[-1]]


@dataclass
class PredictorInputs:
    sex: str
    age_years: float
    current_height_cm: float
    father_height_cm: float
    mother_height_cm: float

    # Maturity — MALE (Band A only).
    voice_depth: int = 0       # 0 high, 1 cracking, 2 deep
    facial_hair: int = 0       # 0 none, 1 peach fuzz, 2 full
    body_hair: int = 0         # 0 none, 1 sparse, 2 full (used for both sexes)
    adams_apple: int = 0       # 0 not visible, 1 visible

    # Maturity — FEMALE (Band A only).
    menarche_status: int = 0   # 0 not started, 1 <1yr, 2 1-2yr, 3 >2yr
    growth_spurt_status: int = 0  # 0 growing fast, 1 slowing, 2 stopped (velocity context only)

    # Both sexes.
    recent_growth_cm: Optional[float] = None  # cm taller in last 12 months

    # Optional tape measure (no penalty if skipped).
    wingspan_cm: Optional[float] = None
    wrist_circumference_cm: Optional[float] = None

    # Optional refinement (analytics only in v2; not used in the height math).
    weight_kg: Optional[float] = None
    shoe_size: Optional[float] = None


def fraction_attained(biological_age: float, sex: str) -> float:
    table = FRACTION_ATTAINED_MALE if _is_male(sex) else FRACTION_ATTAINED_FEMALE
    return _interp_table(table, clamp(biological_age, BIO_AGE_MIN, BIO_AGE_MAX))


def expected_maturity(age: float, sex: str) -> float:
    table = EXPECTED_MATURITY_MALE if _is_male(sex) else EXPECTED_MATURITY_FEMALE
    return _interp_table(table, age)


def expected_growth(age: float, sex: str) -> float:
    table = EXPECTED_GROWTH_MALE if _is_male(sex) else EXPECTED_GROWTH_FEMALE
    return _interp_table(table, age)


def compute_mph(sex: str, father_cm: float, mother_cm: float) -> float:
    """STEP 1 — Mid-parent (genetic anchor)."""
    adj = MPH_SEX_ADJUST_CM if _is_male(sex) else -MPH_SEX_ADJUST_CM
    return (float(father_cm) + float(mother_cm) + adj) / 2.0


def compute_maturity(inp: PredictorInputs) -> float:
    """STEP 2 — sex-specific maturity score (0-10)."""
    if _is_male(inp.sex):
        return (
            clamp(int(inp.voice_depth or 0), 0, 2) * 2.0
            + clamp(int(inp.facial_hair or 0), 0, 2) * 1.5
            + clamp(int(inp.body_hair or 0), 0, 2) * 1.0
            + clamp(int(inp.adams_apple or 0), 0, 1) * 1.0
        )
    menarche_idx = int(clamp(int(inp.menarche_status or 0), 0, 3))
    menarche_points = MENARCHE_POINTS[menarche_idx]
    return menarche_points * 0.8 + clamp(int(inp.body_hair or 0), 0, 2) * 1.0


def _band_for_age(age: float) -> str:
    if age < BAND_A_MAX_EXCLUSIVE:
        return "A"
    if age <= BAND_B_MAX_INCLUSIVE:
        return "B"
    return "20+"


def _w_maturity(age: float) -> float:
    return clamp(W_MATURITY_BASE + (age - 13.0) * W_MATURITY_SLOPE, W_MATURITY_MIN, W_MATURITY_MAX)


def _frame_adj(current_height_cm: float, wrist_cm: Optional[float]) -> float:
    if not wrist_cm or float(wrist_cm) <= 0:
        return 0.0
    ratio = float(current_height_cm) / float(wrist_cm)
    if ratio < FRAME_LARGE_RATIO:
        return FRAME_LARGE_ADJ
    if ratio > FRAME_SMALL_RATIO:
        return FRAME_SMALL_ADJ
    return 0.0


def _wing_adj(current_height_cm: float, wingspan_cm: Optional[float]) -> float:
    if not wingspan_cm or float(wingspan_cm) <= 0:
        return 0.0
    ape_index = float(wingspan_cm) - float(current_height_cm)
    return WING_ADJ if ape_index > APE_INDEX_THRESHOLD else 0.0


def predict_optimized_height(inp: PredictorInputs, posture_recovery_cm: float) -> dict:
    """
    Run the full v2 model (Part 9 pseudocode). Bands A/B/20+ are handled by the same flow:
    maturity adjustment only applies under 17.5; velocity applies whenever recent growth is
    given; for 20+ genetic growth is finished so only posture is added.

    `posture_recovery_cm` is the existing recoverable-loss number — passed in, never recomputed.
    """
    age = float(inp.age_years)
    current = float(inp.current_height_cm)
    posture = max(0.0, float(posture_recovery_cm or 0.0))
    band = _band_for_age(age)

    # 20+ — genetic growth done; posture-only optimization (Part 6).
    if band == "20+":
        true_optimized = current + posture
        return {
            "model_version": MODEL_VERSION,
            "band": band,
            "mph_cm": round(compute_mph(inp.sex, inp.father_height_cm, inp.mother_height_cm), 2),
            "maturity": None,
            "biological_age": None,
            "fraction_attained": None,
            "height_est_maturity_cm": None,
            "w_maturity": None,
            "genetic_potential_cm": round(current, 2),
            "frame_adj_cm": 0.0,
            "wing_adj_cm": 0.0,
            "posture_recovery_cm": round(posture, 2),
            "true_optimized_cm": round(true_optimized, 1),
            "floor_applied": True,
        }

    # STEP 1 — genetic anchor.
    mph = compute_mph(inp.sex, inp.father_height_cm, inp.mother_height_cm)

    # STEP 2-3 — maturity -> biological age (Band A only; Band B skips maturity).
    maturity: Optional[float] = None
    if band == "A":
        maturity = compute_maturity(inp)
        exp_mat = expected_maturity(age, inp.sex)
        bio_offset = clamp((maturity - exp_mat) * MATURITY_FACTOR, -MATURITY_OFFSET_CLAMP, MATURITY_OFFSET_CLAMP)
        bio_age = age + bio_offset
    else:
        bio_age = age

    # STEP 4 — velocity refinement (optional, whenever recent growth provided).
    if inp.recent_growth_cm is not None:
        g_delta = float(inp.recent_growth_cm) - expected_growth(age, inp.sex)
        bio_age -= clamp(g_delta * VELOCITY_FACTOR, -VELOCITY_CLAMP, VELOCITY_CLAMP)

    bio_age = clamp(bio_age, BIO_AGE_MIN, BIO_AGE_MAX)

    # STEP 5-6 — fraction attained + maturity-based estimate.
    frac = fraction_attained(bio_age, inp.sex)
    height_est = current / frac if frac > 0 else current

    # STEP 7 — blend.
    w = _w_maturity(age)
    genetic = w * height_est + (1.0 - w) * mph

    # STEP 8 — optional tape refinements.
    frame_adj = _frame_adj(current, inp.wrist_circumference_cm)
    wing_adj = _wing_adj(current, inp.wingspan_cm)
    genetic = genetic + frame_adj + wing_adj

    # STEP 9-10 — assemble + floor.
    true_optimized = genetic + posture
    min_height = current + posture
    floor_applied = true_optimized < min_height
    true_optimized = max(true_optimized, min_height)

    return {
        "model_version": MODEL_VERSION,
        "band": band,
        "mph_cm": round(mph, 2),
        "maturity": round(maturity, 3) if maturity is not None else None,
        "biological_age": round(bio_age, 3),
        "fraction_attained": round(frac, 4),
        "height_est_maturity_cm": round(height_est, 2),
        "w_maturity": round(w, 4),
        "genetic_potential_cm": round(genetic, 2),
        "frame_adj_cm": round(frame_adj, 2),
        "wing_adj_cm": round(wing_adj, 2),
        "posture_recovery_cm": round(posture, 2),
        "true_optimized_cm": round(true_optimized, 1),
        "floor_applied": floor_applied,
    }
