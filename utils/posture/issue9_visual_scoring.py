from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), float(x)))


def _opt_pct(current_loss_cm: float, max_loss_cm: float) -> float:
    if max_loss_cm <= 0:
        return 100.0
    pct = (1.0 - (float(current_loss_cm) / float(max_loss_cm))) * 100.0
    return float(_clamp(pct, 0.0, 100.0))


ISSUE9_BASELINE_CM = 0.5
ISSUE9_MIN_TOTAL_LOSS_CM = 0.5
ISSUE9_MAX_TOTAL_LOSS_CM = 6.0

ISSUE9_MAX_LOSS = {"spinal": 3.0, "collapse": 2.5, "pelvic": 1.5, "legs": 1.0}

# Q8 multipliers by score (A..D maps to 0..3)
ISSUE9_Q8_MULTIPLIERS = {"A": 1.00, "B": 0.90, "C": 0.75, "D": 0.50}

# Loss (cm) tables, from `questionaire issue9.docx` extracted spec.
ISSUE9_LOSS: Dict[str, Dict[str, float]] = {
    "q1": {"A": 0.1, "B": 0.7, "C": 1.0, "D": 1.3},
    "q2": {"A": 0.1, "B": 0.9, "C": 1.4, "D": 2.0},
    "q3": {"A": 0.1, "B": 0.3, "C": 0.5, "D": 0.7},
    "q4": {"A": 0.1, "B": 0.7, "C": 1.0, "D": 1.3},
    "q5": {"A": 0.1, "B": 0.6, "C": 0.9, "D": 0.6},  # critical: D = 0.6
    "q6": {"A": 0.1, "B": 0.4, "C": 0.7, "D": 1.0},
    "q7": {"A": 0.1, "B": 0.5, "C": 0.7, "D": 1.0},
}


def compute_issue9_visual_results(answers: Dict[str, str]) -> Dict:
    """
    Compute Issue9 visual questionnaire outputs.

    answers: {"q1":"A".."D", ... "q8":"A".."D"} (case-insensitive)
    """
    def _norm_letter(v: str) -> str:
        s = (v or "").strip().upper()
        return s[:1] if s else ""

    a = {k: _norm_letter(v) for k, v in (answers or {}).items()}
    # required q1..q8
    for k in ("q1", "q2", "q3", "q4", "q5", "q6", "q7", "q8"):
        if a.get(k) not in ("A", "B", "C", "D"):
            raise ValueError(f"Missing/invalid answer for {k}")

    q_loss = {k: float(ISSUE9_LOSS[k][a[k]]) for k in ISSUE9_LOSS.keys()}
    baseline = float(ISSUE9_BASELINE_CM)
    raw_loss = baseline + sum(q_loss.values())  # q1..q7 only (q8 excluded)
    total_loss = float(_clamp(raw_loss, ISSUE9_MIN_TOTAL_LOSS_CM, ISSUE9_MAX_TOTAL_LOSS_CM))

    multiplier = float(ISSUE9_Q8_MULTIPLIERS[a["q8"]])
    total_recoverable = float(total_loss * multiplier)

    # Step 4 segment distribution (pre-multiplier)
    spinal_loss = (q_loss["q1"] * 0.6) + (q_loss["q3"] * 0.3) + (q_loss["q4"] * 0.2)
    collapse_loss = (q_loss["q1"] * 0.4) + (q_loss["q2"] * 1.0) + (q_loss["q3"] * 0.7)
    pelvic_loss = (q_loss["q4"] * 0.8) + (q_loss["q5"] * 0.9) + (q_loss["q7"] * 0.4)
    legs_loss = (q_loss["q5"] * 0.1) + (q_loss["q6"] * 1.0) + (q_loss["q7"] * 0.6)

    spinal_rec = spinal_loss * multiplier
    collapse_rec = collapse_loss * multiplier
    pelvic_rec = pelvic_loss * multiplier
    legs_rec = legs_loss * multiplier

    segments = {
        "spinal": {
            "loss_cm": round(spinal_rec, 2),
            "opt_pct": round(_opt_pct(spinal_rec, ISSUE9_MAX_LOSS["spinal"]), 2),
            "max_loss": ISSUE9_MAX_LOSS["spinal"],
        },
        "collapse": {
            "loss_cm": round(collapse_rec, 2),
            "opt_pct": round(_opt_pct(collapse_rec, ISSUE9_MAX_LOSS["collapse"]), 2),
            "max_loss": ISSUE9_MAX_LOSS["collapse"],
        },
        "pelvic": {
            "loss_cm": round(pelvic_rec, 2),
            "opt_pct": round(_opt_pct(pelvic_rec, ISSUE9_MAX_LOSS["pelvic"]), 2),
            "max_loss": ISSUE9_MAX_LOSS["pelvic"],
        },
        "legs": {
            "loss_cm": round(legs_rec, 2),
            "opt_pct": round(_opt_pct(legs_rec, ISSUE9_MAX_LOSS["legs"]), 2),
            "max_loss": ISSUE9_MAX_LOSS["legs"],
        },
    }

    # Step 6 ranking (worst = highest loss). Tie-break priority: spinal > collapse > pelvic > legs.
    tie = {"spinal": 4, "collapse": 3, "pelvic": 2, "legs": 1}
    ranked = sorted(
        ["spinal", "collapse", "pelvic", "legs"],
        key=lambda name: (segments[name]["loss_cm"], tie[name]),
        reverse=True,
    )

    structural_loss = float(total_loss * (1.0 - multiplier))

    return {
        "raw_loss_cm": round(raw_loss, 2),
        "total_loss_cm": round(total_loss, 2),
        "total_recoverable_loss_cm": round(total_recoverable, 2),
        "structural_loss_cm": round(structural_loss, 2),
        "segments": segments,
        "ranked_segments": ranked,
        "meta": {"multiplier": round(multiplier, 2), "baseline_cm": ISSUE9_BASELINE_CM},
    }

