from utils.posture.height_helpers import (
    clamp,
    safe_float,
    safe_int
)
from utils.posture.height_constants import POINT_TO_CM

def genetic_mph(sex, father_cm, mother_cm):
    father_cm = safe_float(father_cm)
    mother_cm = safe_float(mother_cm)

    if sex == "male":
        return (father_cm + mother_cm + 13) / 2
    return (father_cm + mother_cm - 13) / 2


def teen_height_free(profile):
    mph = genetic_mph(
        profile.sex,
        profile.father_height_cm,
        profile.mother_height_cm,
    )

    current_height_cm = safe_float(profile.current_height_cm)

    return {
        "genetic_height_cm": round(mph, 1),
        "current_height_cm": round(current_height_cm, 1),
        "optimized_height_cm": None,  # 🔒 locked
    }


def teen_height_paid(profile, optimized_height_cm, total_points):
    genetic_height_cm = genetic_mph(
        profile.sex,
        profile.father_height_cm,
        profile.mother_height_cm,
    )

    growth_max_cm = safe_float(total_points) * POINT_TO_CM

    return {
        "genetic_height_cm": round(genetic_height_cm, 1),
        "optimized_height_cm": round(safe_float(optimized_height_cm), 1),
        "growth_max_cm": round(growth_max_cm, 2),
        "total_height_cm": round(genetic_height_cm + growth_max_cm, 1),
    }
