from utils.posture.height_helpers import (
    clamp,
    safe_float,
    safe_int
)

def compute_wingspan(
    height_cm_input,
    left_wrist_px,
    right_wrist_px,
    head_px,
    feet_px,
    confidence=1.0,
):
    height_px = abs(head_px - feet_px)
    wingspan_px = abs(left_wrist_px - right_wrist_px)

    if height_px <= 0 or confidence < 0.5:
        est = height_cm_input * 1.01
        return {
            "wingspan_cm": clamp(est, height_cm_input - 2, height_cm_input + 2),
            "source": "fallback_height_ratio",
            "confidence": confidence,
        }

    scale = height_cm_input / height_px
    raw = wingspan_px * scale

    return {
        "wingspan_cm": clamp(raw, height_cm_input - 3, height_cm_input + 3),
        "source": "scan",
        "confidence": confidence,
    }
