from utils.posture.height_constants import POINT_TO_CM
from utils.posture.height_helpers import (
    clamp,
    safe_float,
    safe_int
)

def adult_free(current_height_cm):
    return {
        "current_height_cm": round(current_height_cm, 1),
        "target_height_cm": None,  # 🔒
        "height_reclaimed_cm": None,
    }


def adult_paid(
    current_height_cm,
    posture_loss_cm,
    total_points,
):
    current_height_cm = safe_float(current_height_cm, 0)
    posture_loss_cm = safe_float(posture_loss_cm, 0)
    total_points = safe_int(total_points, 0)

    recovered = total_points * POINT_TO_CM
    recovered = min(recovered, posture_loss_cm)

    return {
        "current_height_cm": round(current_height_cm, 1),
        "target_height_cm": round(current_height_cm + posture_loss_cm, 1),
        "height_reclaimed_cm": round(recovered, 2),
        "remaining_cm": round(posture_loss_cm - recovered, 2),
    }