"""Display category labels for exercise cards (Monday C2)."""
from __future__ import annotations

from workouts.exercise_assignment_data import (
    TEEN_ONLY_HGH_NAMES,
    primary_secondary_for_exercise,
    spec_key_for_name,
)

_SEGMENT_LABELS = {
    "spinal": "Spinal Compression",
    "collapse": "Postural Collapse",
    "pelvic": "Pelvic Tilt & Back",
    "legs": "Leg & Hamstring",
}


def _primary_segment_key(exercise) -> str | None:
    if exercise is None:
        return None
    primary, _secondary = primary_secondary_for_exercise(exercise)
    if primary:
        return primary
    pcts = {
        "spinal": int(getattr(exercise, "spinal_pct", 0) or 0),
        "collapse": int(getattr(exercise, "collapse_pct", 0) or 0),
        "pelvic": int(getattr(exercise, "pelvic_pct", 0) or 0),
        "legs": int(getattr(exercise, "legs_pct", 0) or 0),
    }
    if max(pcts.values()) <= 0:
        return None
    return max(pcts, key=pcts.get)


def exercise_category_label(exercise, *, routine_type: str | None = None) -> str:
    """Human-readable pill label for posture/HGH exercise cards."""
    cat = str(getattr(exercise, "category", "") or "").lower()
    rt = str(routine_type or "").lower()
    key = spec_key_for_name(getattr(exercise, "name", "") or "")
    if cat == "hgh" or rt == "hgh" or key in TEEN_ONLY_HGH_NAMES:
        return "HGH Activation"
    seg = _primary_segment_key(exercise)
    if seg:
        return _SEGMENT_LABELS.get(seg, seg.replace("_", " ").title())
    if cat == "posture":
        return "Postural Collapse"
    return cat.replace("_", " ").title() if cat else "General"
