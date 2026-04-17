# from utils.posture.height_helpers import (
#     clamp,
#     safe_float,
#     safe_int
# )
# from utils.posture.height_constants import POINT_TO_CM

# def genetic_mph(sex, father_cm, mother_cm):
#     father_cm = safe_float(father_cm)
#     mother_cm = safe_float(mother_cm)

#     if sex == "male":
#         return (father_cm + mother_cm + 13) / 2
#     return (father_cm + mother_cm - 13) / 2


# def teen_height_free(profile):
#     mph = genetic_mph(
#         profile.sex,
#         profile.father_height_cm,
#         profile.mother_height_cm,
#     )

#     current_height_cm = safe_float(profile.current_height_cm)

#     return {
#         "genetic_height_cm": round(mph, 1),
#         "current_height_cm": round(current_height_cm, 1),
#         "optimized_height_cm": None,  # 🔒 locked
#     }


# def teen_height_paid(profile, optimized_height_cm, total_points):
#     genetic_height_cm = genetic_mph(
#         profile.sex,
#         profile.father_height_cm,
#         profile.mother_height_cm,
#     )

#     growth_max_cm = safe_float(total_points) * POINT_TO_CM

#     return {
#         "genetic_height_cm": round(genetic_height_cm, 1),
#         "optimized_height_cm": round(safe_float(optimized_height_cm), 1),
#         "growth_max_cm": round(growth_max_cm, 2),
#         "total_height_cm": round(genetic_height_cm + growth_max_cm, 1),
#     }


from utils.posture.height_helpers import (
    clamp,
    safe_float,
)

from utils.posture.height_constants import (
    OPTIMIZATION_GAP_CM,
    POINT_TO_CM,
    PARENT_HEIGHT_CM_MAX,
    PARENT_HEIGHT_CM_MIN,
    USER_HEIGHT_CM_MAX,
    USER_HEIGHT_CM_MIN,
    compute_mph_simple_cm,
    normalize_sex,
)


# -----------------------------------------------------
# GENETIC MPH (Section 2.2 / 5.6 — same formula as compute_mph_simple_cm)
# -----------------------------------------------------
def genetic_mph(sex, father_cm, mother_cm):
    f = clamp(safe_float(father_cm), PARENT_HEIGHT_CM_MIN, PARENT_HEIGHT_CM_MAX)
    m = clamp(safe_float(mother_cm), PARENT_HEIGHT_CM_MIN, PARENT_HEIGHT_CM_MAX)
    s = normalize_sex(sex) or "male"
    return compute_mph_simple_cm(s, f, m)


# -----------------------------------------------------
# FREE VERSION HEIGHT
# -----------------------------------------------------
def teen_height_free(profile):

    genetic_height_cm = genetic_mph(
        profile.sex,
        profile.father_height_cm,
        profile.mother_height_cm,
    )

    current_height_cm = clamp(
        safe_float(profile.current_height_cm),
        USER_HEIGHT_CM_MIN,
        USER_HEIGHT_CM_MAX,
    )

    return {

        "genetic_height_cm": round(genetic_height_cm, 1),

        "current_height_cm": round(current_height_cm, 1),

        # locked feature
        "optimized_height_cm": None,
    }


# -----------------------------------------------------
# PAID VERSION HEIGHT
# -----------------------------------------------------
def teen_height_paid(profile, optimized_height_cm, total_points):

    genetic_height_cm = genetic_mph(
        profile.sex,
        profile.father_height_cm,
        profile.mother_height_cm,
    )

    optimized_height_cm = safe_float(optimized_height_cm)

    growth_max_cm = safe_float(total_points) * POINT_TO_CM
    growth_max_cm = clamp(growth_max_cm, 0.0, OPTIMIZATION_GAP_CM)

    total_height = genetic_height_cm + growth_max_cm

    total_height = clamp(total_height, USER_HEIGHT_CM_MIN, USER_HEIGHT_CM_MAX)

    return {

        "genetic_height_cm": round(genetic_height_cm, 1),

        "optimized_height_cm": round(optimized_height_cm, 1),

        "growth_max_cm": round(growth_max_cm, 2),

        "total_height_cm": round(total_height, 1),
    }