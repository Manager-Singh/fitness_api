"""
TheHeightAppSpec v3.2 — Section 1 global constants (canonical backend source).

1.1 Engine scales are detailed in Section 11; base multipliers:
    Engine 1 (Posture+): 1 point = 0.001 cm. Engine 2 (teens): 1 point = 0.00005 cm.
    The legacy v1 hard cap min(points × 0.001, 0.05) cm/day is removed — do not reapply.

1.2 Segment Max_Loss (cm) is fixed; only Current_Loss comes from scan/questionnaire,
    clamped: Current_Loss[s] = min(Current_Loss[s], Max_Loss[s]).
    Opt_pct: 100 if Max_Loss <= 0 else (1 - Current_Loss/Max_Loss) × 100.

1.3 Optimization_Gap = 5.5 cm — teen PosturePlus lifetime ceiling (Engine 1 cumulative).
    POSTURE_BOOST_MAX_CM = 4.6 cm applies only to Section 5.6 True Optimized Height.

1.4 Daily fields reset at user local midnight (server enforces per log_date);
    cumulatives (ledger-backed) never reset.
"""

from __future__ import annotations

from typing import Any, Dict

# --- Age tiers (Section 2 /12) ---
TEEN_MIN_AGE = 13
TEEN_MAX_AGE = 20
ADULT_MIN_AGE = 21
ADULT_AGE_MAX = 100

# --- Section 2 onboarding + Section 12.4 validation bounds (cm) ---
USER_HEIGHT_CM_MIN = 100
USER_HEIGHT_CM_MAX = 250
PARENT_HEIGHT_CM_MIN = 130
PARENT_HEIGHT_CM_MAX = 250
WINGSPAN_CM_MIN = 100
WINGSPAN_CM_MAX = 250
MPH_SIMPLE_CM_MIN = 100
MPH_SIMPLE_CM_MAX = 250

MSG_USER_HEIGHT_RANGE = "Please enter a height between 100 and 250 cm."
MSG_FATHER_HEIGHT_RANGE = "Please enter a valid height for your father (130–250 cm)."
MSG_MOTHER_HEIGHT_RANGE = "Please enter a valid height for your mother (130–250 cm)."
MSG_WINGSPAN_RANGE = "Please enter a valid arm span (100–250 cm)."
MSG_MPH_OUT_OF_RANGE = (
    "These heights produce an unusual genetic estimate — please double-check your entries."
)
MSG_TEEN_REQUIRES_DOB = "Teen onboarding requires birth_date (YYYY-MM-DD) for exact age calculation."
MSG_TEEN_REQUIRES_PARENTS = "Teen onboarding requires both father_height_cm and mother_height_cm."
MSG_BASE_HEIGHT_LOCKED = "Base height cannot be changed after onboarding."
MSG_ADULT_AGE_RANGE = "Adult age must be between 21 and 100."
MSG_TEEN_UI_AGE_RANGE = "Teen UI age must be between 13 and 20."
MSG_TEEN_DOB_AGE_RANGE = "Date of birth must correspond to age 13–20 for teen accounts."

# --- 1.1 / Section 11 — height gain per point (cm) ---
POINT_TO_CM = 0.001  # legacy alias: Engine 1
POINTS_TO_CM_ENGINE1 = 0.001
POINTS_TO_CM_ENGINE2 = 0.00005

# Documented removed v1 rule (never use for math)
REMOVED_V1_DAILY_HEIGHT_CAP_CM = 0.05

# --- 1.2 — per-segment structural ceiling (cm); sum = 8.0 ---
POSTURE_SEGMENT_MAX_LOSS_CM: Dict[str, float] = {
    "spinal_compression": 3.0,
    "posture_collapse": 2.5,
    "pelvic_tilt_back": 1.5,
    "leg_hamstring": 1.0,
}

# Distribution of Total_Recoverable_Loss across segments (Section 3 / 4)
POSTURE_SEGMENT_DISTRIBUTION_RATIO: Dict[str, float] = {
    "spinal_compression": 0.30,
    "posture_collapse": 0.35,
    "pelvic_tilt_back": 0.25,
    "leg_hamstring": 0.10,
}

TOTAL_STRUCTURAL_CEILING_CM: float = sum(POSTURE_SEGMENT_MAX_LOSS_CM.values())

# --- 1.3 ---
OPTIMIZATION_GAP_CM = 5.5
POSTURE_BOOST_MAX_CM = 4.6

# UI label → canonical code name (Section 1.3; for API metadata / docs)
UI_TO_CODE_VARIABLE_NAMES: Dict[str, str] = {
    "Posture+": "PosturePlus",
    "Genetic+": "Genetic_Daily_Gain",
    "GrowthMax+": "PosturePlus",
    "Daily Gains": "Daily_Gains",
    "Total Recovered": "SUM_Daily_Gains_to_date",
    "True Optimized Height": "Optimized_Height",
}

SCAN_QUALITY_HIGH = "high"
SCAN_QUALITY_MEDIUM = "medium"
SCAN_QUALITY_LOW = "low"


def posture_segment_opt_pct(current_loss_cm: float, max_loss_cm: float) -> int:
    """Section 1.2 / 4.3 optimization bar percentage."""
    if max_loss_cm <= 0:
        return 100
    cur = clamp_current_loss_to_segment_max(current_loss_cm, max_loss_cm)
    pct = int(round((1.0 - cur / float(max_loss_cm)) * 100))
    return max(0, min(100, pct))


def clamp_current_loss_to_segment_max(current_loss_cm: float, max_loss_cm: float) -> float:
    """Section 1.2: clamp current loss to [0, Max_Loss]."""
    if max_loss_cm <= 0:
        return 0.0
    return max(0.0, min(float(max_loss_cm), float(current_loss_cm)))


def normalize_sex(value: Any) -> str | None:
    """Map UI gender to 'male' | 'female' for Section 2 / 5.6 formulas."""
    if value in (None, ""):
        return None
    s = str(value).strip().lower()
    if s in ("male", "m", "man", "boy"):
        return "male"
    if s in ("female", "f", "woman", "girl"):
        return "female"
    return s


def compute_mph_simple_cm(sex: str | None, father_cm: float, mother_cm: float) -> float:
    """
    Section 2.2 — freemium genetic height estimate (same as Section 5.6 MPH base).
    Male: (father + mother + 13) / 2. Female: (father + mother - 13) / 2.
    """
    s = normalize_sex(sex) or "male"
    if s == "female":
        return (float(father_cm) + float(mother_cm) - 13.0) / 2.0
    return (float(father_cm) + float(mother_cm) + 13.0) / 2.0


def default_optimization_breakdown_pending_scan() -> Dict[str, Dict[str, Any]]:
    """
    Section 1.4 initial posture state before scan: zero current loss per segment.
    Section 5.4: pre-scan bars stay at 0% optimization in product UI.
    """
    return {
        seg: {
            "current_loss_cm": 0.0,
            "max_loss_cm": mx,
            "percent_optimized": 0,
        }
        for seg, mx in POSTURE_SEGMENT_MAX_LOSS_CM.items()
    }
