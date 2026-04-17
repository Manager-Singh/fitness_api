# MAX_SEGMENT_LOSS_CM = {
#     "spinal_compression": 3.0,
#     "posture_collapse": 2.5,
#     "pelvic_tilt_back": 1.5,
#     "leg_hamstring": 1.0,
# }

# def calculate_optimization_breakdown(ai_analysis: dict):
#     """
#     Calculates loss and optimization % from either:
#     - ai_analysis["postural_optimization"] (nested)
#     - OR top-level fields directly
#     """
#     scores = ai_analysis.get("postural_optimization") or {
#         "spinal_compression": ai_analysis.get("spinal_compression", 0),
#         "posture_collapse": ai_analysis.get("posture_collapse", 0),
#         "pelvic_tilt_back": ai_analysis.get("pelvic_tilt_back", 0),
#         "leg_hamstring": ai_analysis.get("leg_hamstring", 0),
#     }

#     breakdown = {}
#     for segment, max_loss in MAX_SEGMENT_LOSS_CM.items():
#         score = scores.get(segment, 0)
#         current_loss = round((score / 100) * max_loss, 2)
#         percent_optimized = round((1 - (current_loss / max_loss)) * 100)
#         breakdown[segment] = {
#             "current_loss_cm": current_loss,
#             "max_loss_cm": max_loss,
#             "percent_optimized": percent_optimized
#         }

#     return breakdown


from utils.posture.height_constants import POSTURE_SEGMENT_MAX_LOSS_CM, posture_segment_opt_pct


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def calculate_optimization_breakdown(ai_analysis: dict):
    """
    Calculates loss and optimization % from either:
    - ai_analysis["postural_optimization"] (nested)
    - OR top-level fields directly
    """

    scores = ai_analysis.get("postural_optimization") or {
        "spinal_compression": ai_analysis.get("spinal_compression", 0),
        "posture_collapse": ai_analysis.get("posture_collapse", 0),
        "pelvic_tilt_back": ai_analysis.get("pelvic_tilt_back", 0),
        "leg_hamstring": ai_analysis.get("leg_hamstring", 0),
    }

    breakdown = {}

    for segment, max_loss in POSTURE_SEGMENT_MAX_LOSS_CM.items():
        raw_score = scores.get(segment, 0)

        # ✅ safety
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            score = 0.0

        score = clamp(score, 0.0, 100.0)

        current_loss = round((score / 100.0) * max_loss, 2)

        breakdown[segment] = {
            "current_loss_cm": current_loss,
            "max_loss_cm": max_loss,
            "percent_optimized": posture_segment_opt_pct(current_loss, max_loss),
        }

    return breakdown
