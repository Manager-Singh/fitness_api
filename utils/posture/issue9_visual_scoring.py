from __future__ import annotations

from typing import Dict


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(x)))


def _opt_pct(current_loss_cm: float, max_loss_cm: float) -> float:
    if max_loss_cm <= 0:
        return 100.0
    pct = (1.0 - (float(current_loss_cm) / float(max_loss_cm))) * 100.0
    return float(_clamp(pct, 0.0, 100.0))


# Per POSTURE_LOSS_SCORING_FIX.md (client-signed-off recalibration):
#   - Every question (incl. Q8) ADDS loss. There is no Q8 multiplier.
#   - Options are ordered A (best) -> D (worst); D column sums to exactly 6.0.
#   - total_loss = clamp(sum of 8 values, 0.5, 6.0).
ISSUE9_MIN_TOTAL_LOSS_CM = 0.5
ISSUE9_MAX_TOTAL_LOSS_CM = 6.0

ISSUE9_MAX_LOSS = {"spinal": 3.0, "collapse": 2.5, "pelvic": 1.5, "legs": 1.0}

# New additive per-question loss table. D column sums to 6.0:
# 0.9 + 1.2 + 0.5 + 0.9 + 0.4 + 0.7 + 0.7 + 0.7 = 6.0
ISSUE9_LOSS: Dict[str, Dict[str, float]] = {
    "q1": {"A": 0.0, "B": 0.30, "C": 0.60, "D": 0.90},
    "q2": {"A": 0.0, "B": 0.40, "C": 0.80, "D": 1.20},
    "q3": {"A": 0.0, "B": 0.20, "C": 0.35, "D": 0.50},
    "q4": {"A": 0.0, "B": 0.30, "C": 0.60, "D": 0.90},
    "q5": {"A": 0.0, "B": 0.15, "C": 0.30, "D": 0.40},  # monotonic: D is the worst/most compressive
    "q6": {"A": 0.0, "B": 0.25, "C": 0.50, "D": 0.70},
    "q7": {"A": 0.0, "B": 0.25, "C": 0.50, "D": 0.70},
    "q8": {"A": 0.0, "B": 0.25, "C": 0.50, "D": 0.70},  # Q8 now ADDS loss (no multiplier)
}

# Per-question -> segment distribution (each question's shares sum to 1.0).
# Q1..Q7 keep the existing Issue9 distribution. Q8 (wall-rigidity test:
# flatten neck + upper back) maps to spinal (cervical) + collapse (thoracic).
ISSUE9_SEGMENT_PCT: Dict[str, Dict[str, float]] = {
    "q1": {"spinal": 0.6, "collapse": 0.4},
    "q2": {"collapse": 1.0},
    "q3": {"spinal": 0.3, "collapse": 0.7},
    "q4": {"spinal": 0.2, "pelvic": 0.8},
    "q5": {"pelvic": 0.9, "legs": 0.1},
    "q6": {"legs": 1.0},
    "q7": {"pelvic": 0.4, "legs": 0.6},
    "q8": {"spinal": 0.5, "collapse": 0.5},
}

_SEGMENTS = ("spinal", "collapse", "pelvic", "legs")


def compute_issue9_visual_results(answers: Dict[str, str]) -> Dict:
    """
    Compute Issue9 visual questionnaire outputs (recalibrated spec).

    answers: {"q1":"A".."D", ... "q8":"A".."D"} (case-insensitive)

    Headline == sum of the 4 segment bars, always (reconciliation guaranteed).
    """
    def _norm_letter(v: str) -> str:
        s = (v or "").strip().upper()
        return s[:1] if s else ""

    a = {k: _norm_letter(v) for k, v in (answers or {}).items()}
    for k in ("q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8"):
        if a.get(k) not in ("A", "B", "C", "D"):
            raise ValueError(f"Missing/invalid answer for {k}")

    q_loss = {k: float(ISSUE9_LOSS[k][a[k]]) for k in ISSUE9_LOSS.keys()}

    # raw_loss = sum of the 8 selected option values; clamp to [0.5, 6.0].
    raw_loss = sum(q_loss.values())
    total_loss = float(_clamp(raw_loss, ISSUE9_MIN_TOTAL_LOSS_CM, ISSUE9_MAX_TOTAL_LOSS_CM))

    # Raw per-segment loss from the per-question distribution.
    seg_raw = {s: 0.0 for s in _SEGMENTS}
    for q, shares in ISSUE9_SEGMENT_PCT.items():
        val = q_loss[q]
        for seg, pct in shares.items():
            seg_raw[seg] += val * pct

    # Scale the segment bars so they always add up to the clamped headline.
    if raw_loss > 0:
        factor = total_loss / raw_loss
        seg_loss = {s: seg_raw[s] * factor for s in _SEGMENTS}
    else:
        # All-A edge case (raw_loss == 0): distribute the 0.5 floor across
        # segments by their max ceilings so the bars still sum to total_loss.
        max_sum = sum(ISSUE9_MAX_LOSS[s] for s in _SEGMENTS)
        seg_loss = {s: total_loss * ISSUE9_MAX_LOSS[s] / max_sum for s in _SEGMENTS}

    segments = {
        s: {
            "loss_cm": round(seg_loss[s], 2),
            "opt_pct": round(_opt_pct(seg_loss[s], ISSUE9_MAX_LOSS[s]), 2),
            "max_loss": ISSUE9_MAX_LOSS[s],
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
        "meta": {"multiplier": 1.0, "floor_cm": ISSUE9_MIN_TOTAL_LOSS_CM, "cap_cm": ISSUE9_MAX_TOTAL_LOSS_CM},
    }
