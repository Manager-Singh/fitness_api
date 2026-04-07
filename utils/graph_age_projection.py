# import math

# def calculate_height_projection(current_height, optimized_height, genetic_height, unoptimized_height, gender):
#     """
#     Generate height projections from age 13 to 21 (boys) or 13 to 17 (girls).
    
#     Parameters:
#         current_height: float – current height in cm
#         optimized_height: float
#         genetic_height: float
#         unoptimized_height: float
#         gender: str – 'male' or 'female'
    
#     Returns:
#         dict {
#             'data': {age: {'optimized': ..., 'genetic': ..., 'unoptimized': ...}},
#             'maxY': float (10 cm above highest height)
#         }
#     """
#     gender = gender.lower()

#     if gender == "male":
#         start_percent = 0.88
#         age_range = list(range(13, 22))  # 13 to 21
#         percent_splits = [3.6, 2.6, 1.9, 1.55, 1.1, 0.75, 0.3, 0.2]
#     elif gender == "female":
#         start_percent = 0.96
#         age_range = list(range(13, 18))  # 13 to 17
#         percent_splits = [2.25, 1.25, 0.4, 0.1]
#     else:
#         raise ValueError("Gender must be 'male' or 'female'")

#     def project(final_height):
#         base = round(final_height * start_percent, 2)
#         projections = [base]
#         for p in percent_splits:
#             gain = round(final_height * (p / 100), 2)
#             projections.append(round(projections[-1] + gain, 2))
#         return projections

#     optimized = project(optimized_height)
#     genetic = project(genetic_height)
#     unoptimized = project(unoptimized_height)

#     # Prepare age-wise data
#     result_data = {
#         age: {
#             "optimized": optimized[i],
#             "genetic": genetic[i],
#             "unoptimized": unoptimized[i],
#         }
#         for i, age in enumerate(age_range)
#     }

#     # Find the max height among all projections
#     max_height = max(optimized + genetic + unoptimized)
#     maxY = math.ceil(max_height / 10.0) * 10  # Round up to nearest 10

#     return {
#         "data": result_data,
#         "maxY": maxY
#     }


import math

def calculate_height_projection(
    current_height,
    optimized_height,
    genetic_height,
    unoptimized_height,
    gender
):
    """
    Generate height projections from age 13 to 21 (boys) or 13 to 17 (girls).

    NOTE:
    - If optimized_height or unoptimized_height is None,
      it will safely fall back to genetic_height for math,
      while UI can still lock/hide those lines.
    """
    print('current_height')
    print(current_height)
    print('optimized_height')
    print(optimized_height)
    print('genetic_height')
    print(genetic_height)
    print('unoptimized_height')
    print(unoptimized_height)
    gender = gender.lower()

    if gender == "male":
        start_percent = 0.88
        age_range = list(range(13, 22))
        percent_splits = [3.6, 2.6, 1.9, 1.55, 1.1, 0.75, 0.3, 0.2]
    elif gender == "female":
        start_percent = 0.96
        age_range = list(range(13, 18))
        percent_splits = [2.25, 1.25, 0.4, 0.1]
    else:
        raise ValueError("Gender must be 'male' or 'female'")

    # ─────────────────────────────────────────────
    # SAFE FALLBACKS (KEY FIX)
    # ─────────────────────────────────────────────
    optimized_height = optimized_height if optimized_height is not None else genetic_height
    unoptimized_height = unoptimized_height if unoptimized_height is not None else genetic_height

    def project(final_height):
        base = round(final_height * start_percent, 2)
        projections = [base]
        for p in percent_splits:
            gain = round(final_height * (p / 100), 2)
            projections.append(round(projections[-1] + gain, 2))
        return projections

    optimized = project(optimized_height)
    genetic = project(genetic_height)
    unoptimized = project(unoptimized_height)

    result_data = {
        age: {
            "optimized": optimized[i],
            "genetic": genetic[i],
            "unoptimized": unoptimized[i],
        }
        for i, age in enumerate(age_range)
    }

    max_height = max(optimized + genetic + unoptimized)
    maxY = math.ceil(max_height / 10.0) * 10

    return {
        "data": result_data,
        "maxY": maxY
    }
