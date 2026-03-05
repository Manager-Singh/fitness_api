from utils.posture.height_helpers import safe_float, clamp


def compute_posture_potential_cm(posture_breakdown: dict) -> float:
    """
    posture_breakdown = {
        zone: {
            "current_loss_cm": x,
            "max_loss_cm": y
        }
    }
    """

    if not posture_breakdown:
        return 0.0

    total = 0.0

    for zone_data in posture_breakdown.values():
        total += safe_float(zone_data.get("max_loss_cm", 0))

    # Global safety cap (per your spec)
    return clamp(total, 0.0, 4.0)
