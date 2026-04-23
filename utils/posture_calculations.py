# import json

# # =====================================================
# # HELPERS
# # =====================================================

# def clamp(v, lo, hi):
#     return max(lo, min(hi, v))


# def parse_payload(raw):
#     """
#     Accepts:
#     - dict
#     - JSON string
#     - double-encoded JSON string
#     Returns dict or None
#     """
#     if raw is None:
#         return None

#     parsed = raw
#     try:
#         for _ in range(3):
#             if isinstance(parsed, str):
#                 parsed = json.loads(parsed)
#         if isinstance(parsed, dict):
#             return parsed
#     except Exception:
#         return None

#     return None


# def safe(lm, key, axis):
#     try:
#         return float(lm[key][axis])
#     except Exception:
#         return None


# # =====================================================
# # MAIN POSTURE ANALYSIS (FIXED)
# # =====================================================

# def analyze_posture(front=None, side=None, back=None, t_pose=None):

#     metrics = {
#         "max_height_gain_inches": 0.0,
#         "spinal_compression": 0,
#         "posture_collapse": 0,
#         "pelvic_tilt_back": 0,
#         "leg_hamstring": 0,
#     }

#     # ---------------- SIDE VIEW (SPINE + PELVIS) ----------------
#     if side and isinstance(side, dict) and "landmarks" in side:
#         lm = side["landmarks"]

#         ls = safe(lm, "leftShoulder", "y")
#         rs = safe(lm, "rightShoulder", "y")
#         lh = safe(lm, "leftHip", "y")
#         rh = safe(lm, "rightHip", "y")
#         la = safe(lm, "leftAnkle", "y")
#         ra = safe(lm, "rightAnkle", "y")

#         if None not in (ls, rs, lh, rh, la, ra):
#             shoulder_y = (ls + rs) / 2
#             hip_y = (lh + rh) / 2
#             ankle_y = (la + ra) / 2

#             body_height = abs(ankle_y - shoulder_y)
#             spine_height = abs(hip_y - shoulder_y)

#             if body_height > 0:
#                 spine_ratio = spine_height / body_height
#                 metrics["spinal_compression"] = clamp(
#                     int(spine_ratio * 100), 0, 100
#                 )

#                 pelvic_ratio = abs(lh - rh) / body_height
#                 metrics["pelvic_tilt_back"] = clamp(
#                     int(pelvic_ratio * 120), 0, 100
#                 )

#     # ---------------- FRONT + BACK (SHOULDER SYMMETRY) ----------------
#     diffs = []
#     for view in (front, back):
#         if view and isinstance(view, dict) and "landmarks" in view:
#             lm = view["landmarks"]

#             ls = safe(lm, "leftShoulder", "y")
#             rs = safe(lm, "rightShoulder", "y")
#             la = safe(lm, "leftAnkle", "y")
#             ra = safe(lm, "rightAnkle", "y")

#             if None not in (ls, rs, la, ra):
#                 shoulder_y = (ls + rs) / 2
#                 ankle_y = (la + ra) / 2
#                 body_height = abs(ankle_y - shoulder_y)

#                 if body_height > 0:
#                     diffs.append(abs(ls - rs) / body_height)

#     if diffs:
#         avg_diff = sum(diffs) / len(diffs)
#         metrics["posture_collapse"] = clamp(
#             int(avg_diff * 120), 0, 100
#         )

#     # ---------------- T-POSE / ARM SYMMETRY ----------------
#     ref = t_pose or front
#     if ref and isinstance(ref, dict) and "landmarks" in ref:
#         lm = ref["landmarks"]

#         lw = safe(lm, "leftWrist", "x")
#         rw = safe(lm, "rightWrist", "x")
#         ls = safe(lm, "leftShoulder", "x")
#         rs = safe(lm, "rightShoulder", "x")

#         if None not in (lw, rw, ls, rs):
#             left_arm = abs(lw - ls)
#             right_arm = abs(rw - rs)
#             arm_diff = abs(left_arm - right_arm)

#             metrics["leg_hamstring"] = clamp(
#                 int(arm_diff / 6), 0, 100
#             )

#     # ---------------- HEIGHT POTENTIAL ----------------
#     metrics["max_height_gain_inches"] = round(
#         min(1.5, metrics["spinal_compression"] * 0.015), 2
#     )

#     return metrics


# # =====================================================
# # OPTIMIZATION BREAKDOWN (UNCHANGED, CORRECT)
# # =====================================================

# def build_optimization_breakdown(metrics):

#     MAX = {
#         "spinal_compression": 4.0,
#         "posture_collapse": 3.0,
#         "pelvic_tilt_back": 2.5,
#         "leg_hamstring": 3.5,
#     }

#     SCALE = {
#         "spinal_compression": 100,
#         "posture_collapse": 50,
#         "pelvic_tilt_back": 60,
#         "leg_hamstring": 80,
#     }

#     breakdown = {}

#     for k in MAX:
#         loss = round((metrics[k] / SCALE[k]) * MAX[k], 2)
#         breakdown[k] = {
#             "current_loss_cm": loss,
#             "max_loss_cm": MAX[k],
#             "percent_optimized": clamp(
#                 int(100 - (loss / MAX[k] * 100)), 0, 100
#             ),
#         }

#     return breakdown


# # =====================================================
# # WINGSPAN (SAFE + NORMALIZED)
# # =====================================================

# def compute_wingspan(t_pose, height_cm):

#     if not t_pose or not isinstance(t_pose, dict) or "landmarks" not in t_pose:
#         return {
#             "wingspan_cm": round(height_cm * 1.01, 1),
#             "wingspan_source": "fallback",
#             "wingspan_confidence": 0.3,
#         }

#     lm = t_pose["landmarks"]

#     lw = safe(lm, "leftWrist", "x")
#     rw = safe(lm, "rightWrist", "x")
#     head = safe(lm, "nose", "y")
#     la = safe(lm, "leftAnkle", "y")
#     ra = safe(lm, "rightAnkle", "y")

#     if None in (lw, rw, head, la, ra):
#         return {
#             "wingspan_cm": round(height_cm * 1.01, 1),
#             "wingspan_source": "fallback",
#             "wingspan_confidence": 0.3,
#         }

#     height_px = abs(((la + ra) / 2) - head)
#     if height_px <= 0:
#         return {
#             "wingspan_cm": round(height_cm * 1.01, 1),
#             "wingspan_source": "fallback",
#             "wingspan_confidence": 0.3,
#         }

#     wingspan_px = abs(lw - rw)
#     scale = height_cm / height_px
#     wingspan = clamp(
#         wingspan_px * scale,
#         height_cm - 5,
#         height_cm + 5
#     )

#     return {
#         "wingspan_cm": round(wingspan, 1),
#         "wingspan_source": "scan",
#         "wingspan_confidence": 0.7,
#     }



import json

import logging

logger = logging.getLogger(__name__)

from utils.posture.height_constants import (
    POSTURE_SEGMENT_MAX_LOSS_CM,
    TOTAL_STRUCTURAL_CEILING_CM,
    posture_segment_opt_pct,
)


# =====================================================
# HELPERS
# =====================================================

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def parse_payload(raw):
    """
    Accepts:
    - dict
    - JSON string
    - double-encoded JSON string
    Returns dict or None
    """
    if raw is None:
        return None

    parsed = raw
    try:
        for _ in range(3):
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        logger.exception("parse_payload failed", extra={"raw_type": type(raw).__name__})
        return None

    return None


def safe(lm, key, axis):
    """
    Safely extract a landmark axis value as float.
    """
    try:
        return float(lm[key][axis])
    except Exception:
        logger.exception("safe landmark extract failed", extra={"key": key, "axis": axis})
        return None


def inches_to_cm(inches):
    try:
        return round(float(inches) * 2.54, 2)
    except Exception:
        logger.exception("inches_to_cm failed", extra={"inches": repr(inches)})
        return 0.0


# =====================================================
# MAIN POSTURE ANALYSIS
# =====================================================

def analyze_posture(front=None, side=None, back=None, t_pose=None):
    """
    Returns normalized posture metrics (0–100) and a rough
    max height gain estimate (inches).
    """

    metrics = {
        "max_height_gain_inches": 0.0,
        "spinal_compression": 0,
        "posture_collapse": 0,
        "pelvic_tilt_back": 0,
        "leg_hamstring": 0,
    }
    # ---------------- SIDE VIEW (SPINE + PELVIS) ----------------
    if side and isinstance(side, dict) and "landmarks" in side:
        lm = side["landmarks"]

        ls = safe(lm, "leftShoulder", "y")
        rs = safe(lm, "rightShoulder", "y")
        lh = safe(lm, "leftHip", "y")
        rh = safe(lm, "rightHip", "y")
        la = safe(lm, "leftAnkle", "y")
        ra = safe(lm, "rightAnkle", "y")

        if None not in (ls, rs, lh, rh, la, ra):
            shoulder_y = (ls + rs) / 2
            hip_y = (lh + rh) / 2
            ankle_y = (la + ra) / 2

            body_height = abs(ankle_y - shoulder_y)
            spine_height = abs(hip_y - shoulder_y)

            if body_height > 0:
                spine_ratio = spine_height / body_height
                metrics["spinal_compression"] = clamp(
                    int(spine_ratio * 100), 0, 100
                )

                pelvic_ratio = abs(lh - rh) / body_height
                metrics["pelvic_tilt_back"] = clamp(
                    int(pelvic_ratio * 120), 0, 100
                )

    # ---------------- FRONT + BACK (SHOULDER SYMMETRY) ----------------
    diffs = []
    for view in (front, back):
        if view and isinstance(view, dict) and "landmarks" in view:
            lm = view["landmarks"]

            ls = safe(lm, "leftShoulder", "y")
            rs = safe(lm, "rightShoulder", "y")
            la = safe(lm, "leftAnkle", "y")
            ra = safe(lm, "rightAnkle", "y")

            if None not in (ls, rs, la, ra):
                shoulder_y = (ls + rs) / 2
                ankle_y = (la + ra) / 2
                body_height = abs(ankle_y - shoulder_y)

                if body_height > 0:
                    diffs.append(abs(ls - rs) / body_height)

    if diffs:
        avg_diff = sum(diffs) / len(diffs)
        metrics["posture_collapse"] = clamp(
            int(avg_diff * 120), 0, 100
        )

    # ---------------- T-POSE / ARM SYMMETRY ----------------
    ref = t_pose or front
    if ref and isinstance(ref, dict) and "landmarks" in ref:
        lm = ref["landmarks"]

        lw = safe(lm, "leftWrist", "x")
        rw = safe(lm, "rightWrist", "x")
        ls = safe(lm, "leftShoulder", "x")
        rs = safe(lm, "rightShoulder", "x")

        if None not in (lw, rw, ls, rs):
            left_arm = abs(lw - ls)
            right_arm = abs(rw - rs)
            arm_diff = abs(left_arm - right_arm)

            metrics["leg_hamstring"] = clamp(
                int(arm_diff / 6), 0, 100
            )

    # ---------------- HEIGHT POTENTIAL (ROUGH, INCHES) ----------------
    metrics["max_height_gain_inches"] = round(
        min(1.5, metrics["spinal_compression"] * 0.015), 2
    )
    return metrics


# =====================================================
# OPTIMIZATION BREAKDOWN (SEGMENT-BASED, CM)
# =====================================================

def build_optimization_breakdown(metrics):
    """
    Converts normalized metrics (0–100) into
    per-segment loss in cm and optimization %.
    """
    breakdown = {}

    for k, max_cm in POSTURE_SEGMENT_MAX_LOSS_CM.items():
        raw = metrics.get(k, 0)
        try:
            score = float(raw)
        except Exception:
            score = 0.0

        score = clamp(score, 0.0, 100.0)

        loss = round((score / 100.0) * max_cm, 2)

        breakdown[k] = {
            "current_loss_cm": loss,
            "max_loss_cm": max_cm,
            "percent_optimized": posture_segment_opt_pct(loss, max_cm),
        }

    return breakdown


def compute_posture_potential_cm(breakdown: dict) -> float:
    """
    Sum of per-segment current loss (cm), each clamped to that segment's Max_Loss.
    Capped at Section 1.2 structural ceiling (8.0 cm total across segments).
    """
    if not breakdown:
        return 0.0

    total = 0.0
    for v in breakdown.values():
        try:
            cur = float(v.get("current_loss_cm", 0) or 0)
        except (TypeError, ValueError):
            cur = 0.0
        try:
            mx = float(v.get("max_loss_cm", 0) or 0)
        except (TypeError, ValueError):
            mx = 0.0
        total += clamp(cur, 0.0, mx if mx > 0 else 0.0)

    return clamp(round(total, 2), 0.0, TOTAL_STRUCTURAL_CEILING_CM)


# =====================================================
# WINGSPAN (SAFE + NORMALIZED)
# =====================================================

def compute_wingspan(t_pose, height_cm):
    """
    Returns wingspan in cm with source and confidence.
    """

    try:
        height_cm = float(height_cm)
    except Exception:
        height_cm = 0.0

    if not t_pose or not isinstance(t_pose, dict) or "landmarks" not in t_pose:
        return {
            "wingspan_cm": round(height_cm * 1.01, 1),
            "wingspan_source": "fallback",
            "wingspan_confidence": 0.3,
        }

    lm = t_pose["landmarks"]

    lw = safe(lm, "leftWrist", "x")
    rw = safe(lm, "rightWrist", "x")
    head = safe(lm, "nose", "y")
    la = safe(lm, "leftAnkle", "y")
    ra = safe(lm, "rightAnkle", "y")

    if None in (lw, rw, head, la, ra):
        return {
            "wingspan_cm": round(height_cm * 1.01, 1),
            "wingspan_source": "fallback",
            "wingspan_confidence": 0.3,
        }

    height_px = abs(((la + ra) / 2) - head)
    if height_px <= 0:
        return {
            "wingspan_cm": round(height_cm * 1.01, 1),
            "wingspan_source": "fallback",
            "wingspan_confidence": 0.3,
        }

    wingspan_px = abs(lw - rw)
    scale = height_cm / height_px

    wingspan = clamp(
        wingspan_px * scale,
        height_cm - 5,
        height_cm + 5,
    )

    return {
        "wingspan_cm": round(wingspan, 1),
        "wingspan_source": "scan",
        "wingspan_confidence": 0.7,
    }
