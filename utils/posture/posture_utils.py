from utils.posture.height_helpers import safe_float, clamp


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

    
    print('posture_breakdown')
    print(posture_breakdown)

    weights = {
        "spinal_compression": 1.0,
        "posture_collapse": 0.8,
        "pelvic_tilt_back": 0.6,
        "leg_hamstring": 0.4,
    }

    total = 0.0

    for zone, zone_data in posture_breakdown.items():
        loss = safe_float(zone_data.get("current_loss_cm", 0))
        weight = weights.get(zone, 1.0)
        total += loss * weight

    
    print('posture_potential_cm')
    print(total)

    return clamp(total, 0.0, 4.0)