"""
Adult dashboard live-update payload for POST /api/workout-logs and POST /api/nutra-logs.

Returns ledger-backed height/recovery and runtime posture segments so the client can
refresh dashboard widgets without a full GET /dashboard-new round-trip.
"""
from django.db.models import Sum

from nutration.models_log import NutraEntry
from user_profile.models import UserProfile
from users.models import DailyLog, HeightLedger
from users.spec_runtime import LEDGER_ENTRY_DAILY_COMPUTE, get_user_runtime_state_snapshot
from utils.adult_nutrition import adult_disc_muscle_food_id_sets, adult_engine_nutrition_points
from utils.age import get_user_age, get_user_age_exact
from utils.check_payment import check_subscription_or_response
from utils.monetization_gate import compute_monetization_flags
from utils.posture.diagnostics_contract import build_posture_optimization_diagnostics
from utils.posture.height_constants import POINTS_TO_CM_ENGINE1
from utils.user_time import user_today
from workouts.models import RoutineType, WorkoutEntry

_SEGMENT_SHORT_KEYS = {
    "spinal_compression": "spinal",
    "posture_collapse": "collapse",
    "pelvic_tilt_back": "pelvic",
    "leg_hamstring": "legs",
}


def _adult_base_height_cm(user):
    try:
        prof = UserProfile.objects.filter(user=user).only("base_height_cm", "current_height_cm").first()
        if prof and prof.base_height_cm not in (None, ""):
            return float(prof.base_height_cm)
        if prof and prof.current_height_cm not in (None, ""):
            return float(prof.current_height_cm)
    except Exception:
        pass
    return 0.0


def _live_cumulative_um(user):
    runtime = get_user_runtime_state_snapshot(user) or {}
    cum = runtime.get("current_height_um")
    if cum is not None:
        return max(0, int(cum))
    row = (
        HeightLedger.objects.filter(
            user=user,
            entry_type=LEDGER_ENTRY_DAILY_COMPUTE,
        )
        .order_by("-log_date", "-created_at")
        .only("cumulative_um")
        .first()
    )
    return max(0, int(row.cumulative_um)) if row else 0


def _today_engine_points(user, log_date):
    posture_pts = float(
        WorkoutEntry.objects.filter(
            session__user=user,
            session__date=log_date,
            session__user_routine__routine_type=RoutineType.POSTURE,
        ).aggregate(total=Sum("points"))["total"]
        or 0.0
    )
    entries = NutraEntry.objects.filter(
        session__user=user,
        session__date=log_date,
        food__isnull=False,
    ).select_related("module")
    disc_ids, muscle_ids = adult_disc_muscle_food_id_sets(entries)
    exercise_logged = WorkoutEntry.objects.filter(session__user=user, session__date=log_date).exists()
    nutrition_pts = (
        float(adult_engine_nutrition_points(posture_pts, disc_ids, muscle_ids))
        if exercise_logged
        else 0.0
    )
    return posture_pts, nutrition_pts


def build_adult_dashboard_live_payload(user, log_date=None):
    """
    Build Issue #3 live dashboard fields for adults (21+).

    Returns None for teen accounts so callers can omit the block.
    """
    try:
        age = int(get_user_age(user) or 0)
    except Exception:
        age = 0
    if age < 21:
        return None

    log_date = log_date or user_today(user)
    subscription_data = check_subscription_or_response(user).data
    monetization = compute_monetization_flags(
        age,
        subscription_data,
        age_exact=get_user_age_exact(user),
    )
    conversion_enabled = bool(monetization.get("conversion_enabled"))

    posture_pts, nutrition_pts = _today_engine_points(user, log_date)
    today_daily_points = int(round(posture_pts + nutrition_pts))

    if conversion_enabled:
        today_posture_plus_gain_cm = round(posture_pts * POINTS_TO_CM_ENGINE1, 4)
        today_total_gain_cm = round((posture_pts + nutrition_pts) * POINTS_TO_CM_ENGINE1, 4)
    else:
        today_posture_plus_gain_cm = 0.0
        today_total_gain_cm = 0.0

    base_cm = _adult_base_height_cm(user)
    cum_um = _live_cumulative_um(user)
    total_recovered_cm = round(cum_um / 10000.0, 4)
    current_height_cm = round(base_cm + (cum_um / 10000.0), 4)

    diagnostics = build_posture_optimization_diagnostics(user=user, optimization_breakdown=None)
    segments = {}
    for long_key, short_key in _SEGMENT_SHORT_KEYS.items():
        seg_payload = (diagnostics.get("segments") or {}).get(long_key) or {}
        opt = seg_payload.get("percent_optimized_precise", seg_payload.get("percent_optimized", 0))
        segments[short_key] = {
            "loss_cm": round(float(seg_payload.get("current_loss_cm", 0) or 0), 2),
            "opt_pct": round(float(opt or 0), 2),
        }

    # Keep daily points aligned with engine routing when present.
    daily = DailyLog.objects.filter(user=user, log_date=log_date).only("engine1_points").first()
    if daily and int(daily.engine1_points or 0) > 0:
        today_daily_points = int(daily.engine1_points)

    return {
        "today_daily_points": today_daily_points,
        "today_posture_plus_gain_cm": today_posture_plus_gain_cm,
        "today_total_gain_cm": today_total_gain_cm,
        "current_height_cm": current_height_cm,
        "total_recovered_cm": total_recovered_cm,
        "segments": segments,
    }
