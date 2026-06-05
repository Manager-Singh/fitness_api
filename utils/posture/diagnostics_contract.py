from datetime import timedelta

from django.utils import timezone

from users.spec_runtime import get_user_runtime_state_snapshot
from utils.posture.height_constants import POSTURE_SEGMENT_MAX_LOSS_CM, posture_segment_opt_pct, posture_segment_opt_pct_precise


def _segment_payload(current_loss_cm, max_loss_cm):
    current = max(0.0, min(float(max_loss_cm), float(current_loss_cm)))
    return {
        "current_loss_cm": round(current, 2),
        "max_loss_cm": float(max_loss_cm),
        "percent_optimized": posture_segment_opt_pct(current_loss_cm, max_loss_cm),
        "percent_optimized_precise": posture_segment_opt_pct_precise(current_loss_cm, max_loss_cm, decimals=2),
    }


def build_posture_optimization_diagnostics(
    user,
    optimization_breakdown=None,
    source="pending_scan",
    rescan_days=7,
):
    runtime = get_user_runtime_state_snapshot(user)
    last_scan_at = runtime.get("last_scan_at")
    days_since_scan = None
    if last_scan_at:
        days_since_scan = (timezone.now().date() - last_scan_at.date()).days
    re_scan_timer_days = None if days_since_scan is None else max(0, int(rescan_days) - int(days_since_scan))
    next_scan_at = None if last_scan_at is None else (last_scan_at + timedelta(days=int(rescan_days)))

    # Keep FULL micrometre precision here. Per POSTURE_BARS_DIRECTIVE.md the
    # precise bars must reflect sub-0.01cm recovery (1 logged point moves the
    # Legs bar ~0.01%); rounding to 2dp (=100um) up front froze that movement.
    runtime_segments = {
        "spinal_compression": float(runtime.get("spinal_current_loss_um", 0)) / 10000.0,
        "posture_collapse": float(runtime.get("collapse_current_loss_um", 0)) / 10000.0,
        "pelvic_tilt_back": float(runtime.get("pelvic_current_loss_um", 0)) / 10000.0,
        "leg_hamstring": float(runtime.get("legs_current_loss_um", 0)) / 10000.0,
    }

    # Section 4.3: after unlock, bars must reflect live PostureState (Engine-1 recovery),
    # not a frozen AI/pending_scan snapshot. Treat reconciliation assessment as unlock too.
    has_assessment = bool(str(runtime.get("assessment_sources_used") or "").strip())
    unlocked = bool(
        runtime.get("scan_completed")
        or runtime.get("questionnaire_completed")
        or has_assessment
    )
    has_live_loss_state = (
        float(runtime.get("total_recoverable_loss_um", 0) or 0) > 0
        or sum(runtime_segments.values()) > 0
    )
    use_live_segment_loss = unlocked and has_live_loss_state

    segments = {}
    for seg, max_loss in POSTURE_SEGMENT_MAX_LOSS_CM.items():
        live_loss = float(runtime_segments[seg])
        if use_live_segment_loss:
            seg_current = live_loss
        elif optimization_breakdown and seg in optimization_breakdown:
            bd_loss = float(optimization_breakdown[seg].get("current_loss_cm", live_loss) or 0)
            # Do not let all-zero stale breakdown override real PostureState losses.
            if live_loss > 0 and bd_loss <= 0:
                seg_current = live_loss
            else:
                seg_current = bd_loss
        else:
            seg_current = live_loss
        segments[seg] = _segment_payload(seg_current, max_loss)

    total_current_loss_cm = round(sum(v["current_loss_cm"] for v in segments.values()), 2)
    total_recoverable_loss_cm = round(float(runtime.get("total_recoverable_loss_um", 0)) / 10000.0, 2)
    if total_recoverable_loss_cm <= 0:
        total_recoverable_loss_cm = total_current_loss_cm

    return {
        "scan_completed": bool(runtime.get("scan_completed")),
        "source": source,
        "total_recoverable_loss_cm": total_recoverable_loss_cm,
        "total_current_loss_cm": total_current_loss_cm,
        "segments": segments,
        "re_scan_timer_days": re_scan_timer_days,
        "last_scan_at": last_scan_at,
        "next_scan_at": next_scan_at,
    }
