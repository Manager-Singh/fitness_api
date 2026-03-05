from utils.posture.height_helpers import (
    clamp,
    safe_float,
    safe_int
)
from utils.posture.height_constants import (
    SCAN_QUALITY_HIGH,
    SCAN_QUALITY_MEDIUM,
    SCAN_QUALITY_LOW,
)

def compute_scan_density(
    n_valid,
    n_total,
    has_head,
    has_left_foot,
    has_right_foot,
    fill_ratio=None,
):
    coverage = n_valid / n_total if n_total else 0
    vertical_ok = 1 if (has_head and has_left_foot and has_right_foot) else 0

    if fill_ratio is not None:
        raw = 0.6 * coverage + 0.2 * vertical_ok + 0.2 * fill_ratio
    else:
        raw = 0.75 * coverage + 0.25 * vertical_ok

    score = clamp(raw, 0, 1)

    if score >= 0.8:
        bucket = SCAN_QUALITY_HIGH
    elif score >= 0.5:
        bucket = SCAN_QUALITY_MEDIUM
    else:
        bucket = SCAN_QUALITY_LOW

    return {
        "scan_density": score,
        "bucket": bucket,
        "coverage": coverage,
        "vertical_ok": vertical_ok,
    }
