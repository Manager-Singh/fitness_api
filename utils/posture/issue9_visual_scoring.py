from __future__ import annotations

from typing import Dict

from utils.posture.height_constants import (
    POSTURE_SEGMENT_MAX_LOSS_CM,
    REFERENCE_HEIGHT_CM,
    height_scaled_segment_max_loss_cm,
    posture_height_factor,
)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(x)))


def _opt_pct(current_loss_cm: float, max_loss_cm: float) -> float:
    if max_loss_cm <= 0:
        return 100.0
    pct = (1.0 - (float(current_loss_cm) / float(max_loss_cm))) * 100.0
    return float(_clamp(pct, 0.0, 100.0))


ISSUE9_ADULT_MIN_TOTAL_LOSS_CM = 1.0
ISSUE9_TEEN_MIN_TOTAL_LOSS_CM = 0.0
ISSUE9_MAX_TOTAL_LOSS_CM = 8.0

ANSWER_FRACTIONS: Dict[str, float] = {
    "A": 0.0,
    "B": 0.2,
    "C": 0.4,
    "D": 0.6,
    "E": 0.8,
    "F": 1.0,
}

ISSUE9_MAX_LOSS = {
    "spinal": POSTURE_SEGMENT_MAX_LOSS_CM["spinal_compression"],
    "collapse": POSTURE_SEGMENT_MAX_LOSS_CM["posture_collapse"],
    "pelvic": POSTURE_SEGMENT_MAX_LOSS_CM["pelvic_tilt_back"],
    "legs": POSTURE_SEGMENT_MAX_LOSS_CM["leg_hamstring"],
}

_SEGMENTS = ("spinal", "collapse", "pelvic", "legs")


def compute_issue9_visual_results(
    answers: Dict[str, str],
    *,
    height_cm: float | None = None,
    clamp_min_cm: float = ISSUE9_ADULT_MIN_TOTAL_LOSS_CM,
) -> Dict:
    """
    Compute Issue9 visual questionnaire outputs (recalibrated spec).

    answers: {"q1":"A".."F", ... "q8":"A".."F"} (case-insensitive)

    Headline == sum of the 4 segment bars, always (reconciliation guaranteed).
    """
    def _norm_letter(v: str) -> str:
        s = (v or "").strip().upper()
        return s[:1] if s else ""

    a = {k: _norm_letter(v) for k, v in (answers or {}).items()}
    for k in ("q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8"):
        if a.get(k) not in ANSWER_FRACTIONS:
            raise ValueError(f"Missing/invalid answer for {k}")

    f = {k: float(ANSWER_FRACTIONS[a[k]]) for k in a}
    factor = posture_height_factor(height_cm)
    scaled_max_by_key = height_scaled_segment_max_loss_cm(height_cm)
    scaled_max = {
        "spinal": scaled_max_by_key["spinal_compression"],
        "collapse": scaled_max_by_key["posture_collapse"],
        "pelvic": scaled_max_by_key["pelvic_tilt_back"],
        "legs": scaled_max_by_key["leg_hamstring"],
    }

    ref_loss_um = {
        "collapse": ((f["q1"] + f["q2"] + f["q3"] + f["q4"]) / 4.0) * 3000.0,
        "spinal": (f["q7"] * 2000.0) + (f["q8"] * 500.0),
        "pelvic": (f["q5"] * 1200.0) + (f["q8"] * 300.0),
        "legs": f["q6"] * 1000.0,
    }
    seg_loss = {
        "spinal": _clamp(ref_loss_um["spinal"], 0, 2500) * factor / 1000.0,
        "collapse": _clamp(ref_loss_um["collapse"], 0, 3000) * factor / 1000.0,
        "pelvic": _clamp(ref_loss_um["pelvic"], 0, 1500) * factor / 1000.0,
        "legs": _clamp(ref_loss_um["legs"], 0, 1000) * factor / 1000.0,
    }
    raw_loss = sum(seg_loss.values())
    max_total = sum(scaled_max.values())
    total_loss = float(_clamp(raw_loss, clamp_min_cm, max_total))
    if raw_loss > 0 and total_loss != raw_loss:
        scale = total_loss / raw_loss
        seg_loss = {s: min(scaled_max[s], seg_loss[s] * scale) for s in _SEGMENTS}
    elif raw_loss <= 0 and total_loss > 0:
        max_sum = sum(scaled_max.values())
        seg_loss = {s: total_loss * scaled_max[s] / max_sum for s in _SEGMENTS}

    segments = {
        s: {
            "loss_cm": round(seg_loss[s], 2),
            "opt_pct": round(_opt_pct(seg_loss[s], scaled_max[s]), 2),
            "max_loss": round(scaled_max[s], 4),
        }
        for s in _SEGMENTS
    }

    # Ranking (worst = highest loss). Tie-break: spinal > collapse > pelvic > legs.
    tie = {"spinal": 4, "collapse": 3, "pelvic": 2, "legs": 1}
    ranked = sorted(
        list(_SEGMENTS),
        key=lambda name: (seg_loss[name], tie[name]),
        reverse=True,
    )

    return {
        "raw_loss_cm": round(raw_loss, 2),
        "total_loss_cm": round(total_loss, 2),
        # Everything is recoverable now (no structural multiplier).
        "total_recoverable_loss_cm": round(total_loss, 2),
        "structural_loss_cm": 0.0,
        "segments": segments,
        "ranked_segments": ranked,
        "meta": {
            "answer_fractions": ANSWER_FRACTIONS,
            "reference_height_cm": REFERENCE_HEIGHT_CM,
            "height_cm": height_cm,
            "height_factor": round(factor, 6),
            "floor_cm": clamp_min_cm,
            "cap_cm": round(max_total, 4),
            "ref_loss_um": {k: int(round(v)) for k, v in ref_loss_um.items()},
        },
    }
