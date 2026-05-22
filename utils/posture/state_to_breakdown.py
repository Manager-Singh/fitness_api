"""Convert reconciled PostureState um fields to optimization_breakdown for routine scoring."""
from __future__ import annotations

from typing import Any, Dict

from users.models import PostureState
from utils.posture.height_constants import (
    POSTURE_SEGMENT_MAX_LOSS_CM,
    posture_segment_opt_pct,
)

_STATE_SEGMENT_TO_BREAKDOWN_KEY = {
    "spinal": "spinal_compression",
    "collapse": "posture_collapse",
    "pelvic": "pelvic_tilt_back",
    "legs": "leg_hamstring",
}

_STATE_UM_ATTR = {
    "spinal": "spinal_current_loss_um",
    "collapse": "collapse_current_loss_um",
    "pelvic": "pelvic_current_loss_um",
    "legs": "legs_current_loss_um",
}


def posture_state_to_optimization_breakdown(state: PostureState | None) -> Dict[str, Dict[str, Any]]:
    """Build optimization_breakdown dict from PostureState segment um fields."""
    if state is None:
        return _empty_breakdown()

    out: Dict[str, Dict[str, Any]] = {}
    for seg, key in _STATE_SEGMENT_TO_BREAKDOWN_KEY.items():
        max_cm = float(POSTURE_SEGMENT_MAX_LOSS_CM[key])
        loss_um = int(getattr(state, _STATE_UM_ATTR[seg], 0) or 0)
        current_loss_cm = round(loss_um / 10000.0, 2)
        current_loss_cm = max(0.0, min(max_cm, current_loss_cm))
        out[key] = {
            "current_loss_cm": current_loss_cm,
            "max_loss_cm": max_cm,
            "percent_optimized": posture_segment_opt_pct(current_loss_cm, max_cm),
        }
    return out


def posture_state_snapshot(state: PostureState | None) -> Dict[str, int]:
    """Snapshot segment loss um for routine drift comparison."""
    if state is None:
        return {}
    return {
        "spinal_loss_um": int(state.spinal_current_loss_um or 0),
        "collapse_loss_um": int(state.collapse_current_loss_um or 0),
        "pelvic_loss_um": int(state.pelvic_current_loss_um or 0),
        "legs_loss_um": int(state.legs_current_loss_um or 0),
    }


def breakdown_to_segment_um(optimization_breakdown: dict | None) -> Dict[str, int]:
    """Extract segment losses in um from optimization_breakdown."""
    if not optimization_breakdown:
        return {"spinal": 0, "collapse": 0, "pelvic": 0, "legs": 0, "total": 0}

    mapping = {
        "spinal_compression": "spinal",
        "posture_collapse": "collapse",
        "pelvic_tilt_back": "pelvic",
        "leg_hamstring": "legs",
    }
    segs = {}
    for key, seg in mapping.items():
        payload = optimization_breakdown.get(key) or {}
        cm = float(payload.get("current_loss_cm", 0) or 0)
        segs[seg] = int(round(cm * 10000))

    segs["total"] = segs["spinal"] + segs["collapse"] + segs["pelvic"] + segs["legs"]
    return segs


def posture_bars_to_segment_um(posture_bars: dict) -> Dict[str, int]:
    """Extract segment losses in um from scan posture_bars (spinal/collapse/pelvic/legs keys)."""
    segs = {}
    for seg in ("spinal", "collapse", "pelvic", "legs"):
        bar = posture_bars.get(seg) or {}
        cm = float(bar.get("current_loss_cm", 0) or 0)
        segs[seg] = int(round(cm * 10000))
    segs["total"] = sum(segs[s] for s in ("spinal", "collapse", "pelvic", "legs"))
    return segs


def _empty_breakdown() -> Dict[str, Dict[str, Any]]:
    out = {}
    for key, max_cm in POSTURE_SEGMENT_MAX_LOSS_CM.items():
        out[key] = {
            "current_loss_cm": 0.0,
            "max_loss_cm": max_cm,
            "percent_optimized": 100,
        }
    return out
