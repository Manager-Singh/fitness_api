from dataclasses import dataclass
from typing import Literal, Optional
from datetime import datetime


# =====================================================
# INPUT TYPES
# =====================================================
HeightChange = Literal["0-1", "2-4", "5+"]
GrowthSpeed = Literal["stable", "slow", "fast"]
VoiceStage = Literal["child", "in_between", "deep"]
HairStage = Literal["none", "some", "full"]
LooksStage = Literal["younger", "same", "older"]


# =====================================================
# INPUT MODEL
# =====================================================
@dataclass
class TeenProfile:
    sex: Literal["male", "female"]
    age_years: int
    age_months: int

    current_height_cm: float
    father_height_cm: float
    mother_height_cm: float

    height_change_12m: HeightChange
    shoe_pant_growth: GrowthSpeed
    voice_stage: VoiceStage
    hair_stage: HairStage
    looks_vs_peers: LooksStage

    posture_potential_cm: float  # from posture scan
    last_scan: Optional[datetime]  # datetime of last scan


# =====================================================
# HELPERS
# =====================================================
def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# =====================================================
# 1️⃣ MID-PARENT HEIGHT
# =====================================================
def compute_mph(sex, father_cm, mother_cm):
    father_cm = safe_float(father_cm)
    mother_cm = safe_float(mother_cm)

    if sex == "male":
        return (father_cm + mother_cm + 13) / 2
    return (father_cm + mother_cm - 13) / 2


# =====================================================
# 2️⃣ BIOLOGICAL AGE MODIFIER
# =====================================================
def compute_bio_age_modifier(p: TeenProfile) -> float:
    score = 0

    if p.height_change_12m == "5+":
        score += 1
    elif p.height_change_12m == "0-1":
        score -= 1

    if p.shoe_pant_growth == "fast":
        score += 1
    elif p.shoe_pant_growth == "stable":
        score -= 1

    if p.voice_stage == "child":
        score += 1
    elif p.voice_stage == "deep":
        score -= 1

    if p.hair_stage == "none":
        score += 1
    elif p.hair_stage == "full":
        score -= 1

    if p.looks_vs_peers == "younger":
        score += 1
    elif p.looks_vs_peers == "older":
        score -= 1

    if score >= 3:
        return 3.0
    if score == 2:
        return 2.0
    if score == 1:
        return 1.0
    if score == 0:
        return 0.0
    if score == -1:
        return -1.0
    return -2.0


# =====================================================
# 3️⃣ AGE CAP
# =====================================================
def compute_age_cap(age):
    if age <= 16:
        return 3.5
    if age == 17:
        return 3.0
    if age == 18:
        return 2.0
    if age == 19:
        return 1.0
    return 0.5


# =====================================================
# 4️⃣ GROWTH SCORE (0–1)
# =====================================================
def compute_growth_score(p: TeenProfile):
    score = 0

    if p.height_change_12m == "5+":
        score += 2
    elif p.height_change_12m == "2-4":
        score += 1

    if p.shoe_pant_growth == "fast":
        score += 1
    if p.voice_stage == "child":
        score += 1
    if p.hair_stage == "none":
        score += 1
    if p.looks_vs_peers == "younger":
        score += 1

    return clamp(score / 6.0, 0.0, 1.0)


# =====================================================
# 5️⃣ FINAL OPTIMIZED HEIGHT
# =====================================================
def compute_optimized_height(p: TeenProfile):
    mph = compute_mph(
        p.sex,
        p.father_height_cm,
        p.mother_height_cm,
    )

    bio_age_cm = compute_bio_age_modifier(p)
    base_height_cm = mph + bio_age_cm

    age_cap = compute_age_cap(p.age_years)
    growth_score = compute_growth_score(p)
    growth_window_boost_cm = age_cap * growth_score

    posture_cm = clamp(safe_float(p.posture_potential_cm), 0.0, 4.0)

    optimized_height_cm = (
        base_height_cm +
        growth_window_boost_cm +
        posture_cm
    )

    return {
        "base_height_cm": round(base_height_cm, 1),
        "growth_window_boost_cm": round(growth_window_boost_cm, 1),
        "posture_potential_cm": round(posture_cm, 1),
        "optimized_height_cm": round(optimized_height_cm, 1),
        "mph_height_cm": round(mph, 1),
    }
