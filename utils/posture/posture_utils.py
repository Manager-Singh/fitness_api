from utils.posture.height_helpers import safe_float, clamp
from utils.posture.height_constants import POSTURE_BOOST_MAX_CM


# def compute_posture_potential_cm(posture_breakdown: dict) -> float:
#     """
#     posture_breakdown = {
#         zone: {
#             "current_loss_cm": x,
#             "max_loss_cm": y
#         }
#     }
#     """

#     if not posture_breakdown:
#         return 0.0

#     total = 0.0

#     for zone_data in posture_breakdown.values():
#         total += safe_float(zone_data.get("max_loss_cm", 0))
#     print('max_loss_cm\n')
#     print(total)
#     # Global safety cap (per your spec)
#     return clamp(total, 0.0, 4.0)

def compute_posture_potential_cm(posture_breakdown: dict) -> float:

    if not posture_breakdown:
        return 0.0

    total_ratio = 0.0
    counted_segments = 0

    for zone_data in posture_breakdown.values():
        current_loss = safe_float(zone_data.get("current_loss_cm", 0))
        max_loss = safe_float(zone_data.get("max_loss_cm", 0))

        if max_loss <= 0:
            continue

        loss_ratio = clamp(current_loss / max_loss, 0.0, 1.0)
        total_ratio += loss_ratio
        counted_segments += 1

    if counted_segments == 0:
        return 0.0

    # Section 5.6 — True Optimized Height posture boost (distinct from §1.3 Optimization_Gap 5.5 cm).
    missing_fraction = total_ratio / counted_segments
    posture_boost_cm = POSTURE_BOOST_MAX_CM * missing_fraction

    return clamp(posture_boost_cm, 0.0, POSTURE_BOOST_MAX_CM)