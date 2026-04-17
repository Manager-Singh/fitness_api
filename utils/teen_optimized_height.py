# from dataclasses import dataclass
# from typing import Literal, Optional
# from datetime import datetime


# # =====================================================
# # INPUT TYPES
# # =====================================================
# HeightChange = Literal["0-1", "2-4", "5+"]
# GrowthSpeed = Literal["stable", "slow", "fast"]
# VoiceStage = Literal["child", "in_between", "deep"]
# HairStage = Literal["none", "some", "full"]
# LooksStage = Literal["younger", "same", "older"]


# # =====================================================
# # INPUT MODEL
# # =====================================================
# @dataclass
# class TeenProfile:
#     sex: Literal["male", "female"]
#     age_years: int
#     age_months: int

#     current_height_cm: float
#     father_height_cm: float
#     mother_height_cm: float

#     height_change_12m: HeightChange
#     shoe_pant_growth: GrowthSpeed
#     voice_stage: VoiceStage
#     hair_stage: HairStage
#     looks_vs_peers: LooksStage

#     posture_potential_cm: float  # from posture scan
#     last_scan: Optional[datetime]  # datetime of last scan


# # =====================================================
# # HELPERS
# # =====================================================
# def clamp(v, lo, hi):
#     return max(lo, min(hi, v))


# def safe_float(v, default=0.0):
#     try:
#         return float(v)
#     except (TypeError, ValueError):
#         return default


# # =====================================================
# # 1️⃣ MID-PARENT HEIGHT
# # =====================================================
# def compute_mph(sex, father_cm, mother_cm):
#     father_cm = safe_float(father_cm)
#     mother_cm = safe_float(mother_cm)

#     if sex == "male":
#         return (father_cm + mother_cm + 13) / 2
#     return (father_cm + mother_cm - 13) / 2


# # =====================================================
# # 2️⃣ BIOLOGICAL AGE MODIFIER
# # =====================================================
# def compute_bio_age_modifier(p: TeenProfile) -> float:
#     score = 0

#     if p.height_change_12m == "5+":
#         score += 1
#     elif p.height_change_12m == "0-1":
#         score -= 1

#     if p.shoe_pant_growth == "fast":
#         score += 1
#     elif p.shoe_pant_growth == "stable":
#         score -= 1

#     if p.voice_stage == "child":
#         score += 1
#     elif p.voice_stage == "deep":
#         score -= 1

#     if p.hair_stage == "none":
#         score += 1
#     elif p.hair_stage == "full":
#         score -= 1

#     if p.looks_vs_peers == "younger":
#         score += 1
#     elif p.looks_vs_peers == "older":
#         score -= 1

#     if score >= 3:
#         return 3.0
#     if score == 2:
#         return 2.0
#     if score == 1:
#         return 1.0
#     if score == 0:
#         return 0.0
#     if score == -1:
#         return -1.0
#     return -2.0


# # =====================================================
# # 3️⃣ AGE CAP
# # =====================================================
# def compute_age_cap(age):
#     if age <= 16:
#         return 3.5
#     if age == 17:
#         return 3.0
#     if age == 18:
#         return 2.0
#     if age == 19:
#         return 1.0
#     return 0.5


# # =====================================================
# # 4️⃣ GROWTH SCORE (0–1)
# # =====================================================
# def compute_growth_score(p: TeenProfile):
#     score = 0

#     if p.height_change_12m == "5+":
#         score += 2
#     elif p.height_change_12m == "2-4":
#         score += 1

#     if p.shoe_pant_growth == "fast":
#         score += 1
#     if p.voice_stage == "child":
#         score += 1
#     if p.hair_stage == "none":
#         score += 1
#     if p.looks_vs_peers == "younger":
#         score += 1

#     return clamp(score / 6.0, 0.0, 1.0)


# # =====================================================
# # 5️⃣ FINAL OPTIMIZED HEIGHT
# # =====================================================
# def compute_optimized_height(p: TeenProfile):
#     mph = compute_mph(
#         p.sex,
#         p.father_height_cm,
#         p.mother_height_cm,
#     )

#     bio_age_cm = compute_bio_age_modifier(p)
#     base_height_cm = mph + bio_age_cm

#     age_cap = compute_age_cap(p.age_years)
#     growth_score = compute_growth_score(p)
#     growth_window_boost_cm = age_cap * growth_score

#     posture_cm = clamp(safe_float(p.posture_potential_cm), 0.0, 4.0)

#     optimized_height_cm = (
#         base_height_cm +
#         growth_window_boost_cm +
#         posture_cm
#     )

#     return {
#         "base_height_cm": round(base_height_cm, 1),
#         "growth_window_boost_cm": round(growth_window_boost_cm, 1),
#         "posture_potential_cm": round(posture_cm, 1),
#         "optimized_height_cm": round(optimized_height_cm, 1),
#         "mph_height_cm": round(mph, 1),
#     }

from dataclasses import dataclass
from typing import Literal, Optional
from datetime import datetime

from utils.posture.height_constants import POSTURE_BOOST_MAX_CM


# =====================================================
# INPUT TYPES
# =====================================================
HeightChange = Literal["0-1", "2-4", "5+"]
GrowthSpeed = Literal["stable", "slow", "fast"]
VoiceStage = Literal["child", "in_between", "deep"]
HairStage = Literal["none", "some", "full"]
LooksStage = Literal["younger", "same", "older"]


# =====================================================
# PROFILE MODEL
# =====================================================
@dataclass
class TeenProfile:
    sex: Literal["male", "female"]

    # Decimal years when DOB-backed (Section 5.6); falls back to whole-year profile.age.
    age_years: float
    age_months: int

    current_height_cm: float
    father_height_cm: float
    mother_height_cm: float

    height_change_12m: HeightChange
    shoe_pant_growth: GrowthSpeed
    voice_stage: VoiceStage
    hair_stage: HairStage
    looks_vs_peers: LooksStage

    posture_potential_cm: float
    last_scan: Optional[datetime]

    # Premium scan/questionnaire inputs (spec v3.2 section 5.6).
    voice_depth_score: int = 0
    facial_hair_score: int = 0
    axillary_hair_score: int = 0
    adams_apple_score: int = 0
    wingspan_cm: float = 0.0
    scan_density_result: int = 1
    collapse_score: float = 0.0
    pelvic_score: float = 0.0
    leg_ham_score: float = 0.0
    spinal_score: float = 0.0


# =====================================================
# HELPERS
# =====================================================
def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def safe_float(v, default=0.0):
    try:
        return float(v)
    except:
        return default


def validate_height(height):
    """Section 12.4 — user/onboarding height cm bounds."""
    from utils.posture.height_constants import USER_HEIGHT_CM_MAX, USER_HEIGHT_CM_MIN

    return clamp(height, USER_HEIGHT_CM_MIN, USER_HEIGHT_CM_MAX)


def validate_parent_height(height):
    """Section 12.4 — parent height cm bounds."""
    from utils.posture.height_constants import PARENT_HEIGHT_CM_MAX, PARENT_HEIGHT_CM_MIN

    return clamp(height, PARENT_HEIGHT_CM_MIN, PARENT_HEIGHT_CM_MAX)


# =====================================================
# MID PARENT HEIGHT
# =====================================================
def compute_mph(sex, father_cm, mother_cm):

    father_cm = validate_parent_height(safe_float(father_cm))
    mother_cm = validate_parent_height(safe_float(mother_cm))

    if sex == "male":
        return (father_cm + mother_cm + 13) / 2
    else:
        return (father_cm + mother_cm - 13) / 2


# =====================================================
# BIO AGE MODIFIER
# =====================================================
def compute_puberty_score(p: TeenProfile):
    sex = (p.sex or "").lower()
    if sex == "male":
        return (
            int(clamp(p.voice_depth_score, 0, 2))
            + int(clamp(p.facial_hair_score, 0, 2))
            + int(clamp(p.axillary_hair_score, 0, 2))
            + int(clamp(p.adams_apple_score, 0, 1))
        )
    return (
        int(clamp(p.axillary_hair_score, 0, 2))
        + int(clamp(p.adams_apple_score, 0, 1))
    )


def compute_bio_modifier(p: TeenProfile):
    puberty_score = compute_puberty_score(p)
    age = safe_float(p.age_years)
    sex = (p.sex or "").lower()

    if sex == "male":
        if age >= 16.0 and puberty_score <= 2:
            return 3.0
        if age <= 14.0 and puberty_score >= 5:
            return -2.0
        return 0.0

    if age >= 15.0 and puberty_score <= 0:
        return 1.5
    if age <= 13.0 and puberty_score >= 3:
        return -1.0
    return 0.0


def compute_frame_modifier(scan_density_result):
    return 1.5 if int(scan_density_result) == 2 else 0.0


def compute_wingspan_modifier(wingspan_cm, current_height_cm):
    ape_index = safe_float(wingspan_cm) - safe_float(current_height_cm)
    return 2.0 if ape_index > 5.0 else 0.0


def compute_posture_boost(p: TeenProfile):
    scores = [
        safe_float(p.collapse_score, -1),
        safe_float(p.pelvic_score, -1),
        safe_float(p.leg_ham_score, -1),
        safe_float(p.spinal_score, -1),
    ]
    valid_scores = [score for score in scores if 0.0 <= score <= 100.0]

    if len(valid_scores) == 4:
        avg_posture = sum(valid_scores) / 4.0
        missing_fraction = clamp((100.0 - avg_posture) / 100.0, 0.0, 1.0)
        return round(POSTURE_BOOST_MAX_CM * missing_fraction, 4)

    return clamp(safe_float(p.posture_potential_cm), 0.0, POSTURE_BOOST_MAX_CM)


# =====================================================
# FINAL HEIGHT PREDICTION
# =====================================================
def compute_optimized_height(p: TeenProfile):
    current_height = validate_height(p.current_height_cm)
    mph = compute_mph(
        p.sex,
        p.father_height_cm,
        p.mother_height_cm
    )
    bio_modifier = compute_bio_modifier(p)
    frame_modifier = compute_frame_modifier(p.scan_density_result)
    wingspan_modifier = compute_wingspan_modifier(p.wingspan_cm, current_height)
    posture_gain = compute_posture_boost(p)

    predicted_height = mph + bio_modifier + frame_modifier + wingspan_modifier + posture_gain
    if p.sex == "male":
        predicted_height = clamp(predicted_height, 120, 210)
    else:
        predicted_height = clamp(predicted_height, 120, 195)

    return {
        "current_height_cm": round(current_height, 1),
        "posture_gain_cm": round(posture_gain, 1),
        "bio_age_modifier_cm": round(bio_modifier, 1),
        "frame_modifier_cm": round(frame_modifier, 1),
        "wingspan_modifier_cm": round(wingspan_modifier, 1),
        "puberty_score": compute_puberty_score(p),
        "mph_height_cm": round(mph, 1),
        "optimized_height_cm": round(predicted_height, 1),
    }