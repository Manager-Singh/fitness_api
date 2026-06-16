"""Display category labels for exercise cards (Monday C2)."""
from __future__ import annotations

_SEGMENT_LABELS = {
    "spinal": "Spinal Decompression",
    "collapse": "Postural Correction",
    "pelvic": "Pelvic",
    "legs": "Legs & Hamstrings",
}


def _primary_segment_key(exercise) -> str | None:
    if exercise is None:
        return None
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
    if cat == "hgh" or rt == "hgh":
        return "HGH"
    seg = _primary_segment_key(exercise)
    if seg:
        return _SEGMENT_LABELS.get(seg, seg.replace("_", " ").title())
    if cat == "posture":
        return "Postural Correction"
    return cat.replace("_", " ").title() if cat else "General"
