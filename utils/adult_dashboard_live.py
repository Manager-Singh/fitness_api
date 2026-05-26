"""
Adult dashboard live-update payload for POST /api/workout-logs and POST /api/nutra-logs.

Returns ledger-backed height/recovery and runtime posture segments so the client can
refresh dashboard widgets without a full GET /dashboard-new round-trip.
"""
from django.db.models import Sum

from nutration.models_log import NutraEntry
from users.models import DailyLog
from utils.adult_dashboard_metrics import (
    adult_base_height_cm,
    adult_daily_gains_cm_today,
    adult_engine1_points_today,
    live_cumulative_gain_cm,
    live_height_cm,
)
from utils.adult_nutrition import adult_disc_muscle_food_id_sets, adult_engine_nutrition_points
from utils.age import get_user_age, get_user_age_exact
from utils.check_payment import check_subscription_or_response
from utils.monetization_gate import compute_monetization_flags
from utils.paywall_flags import is_adult_age, is_teen_age
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
    Build Issue #3 live dashboard fields for adult dashboard accounts.

    Adult band is sex-specific (female 18+, male 21+). Returns None for teen accounts.
    """
    age_exact = get_user_age_exact(user)
    try:
        age = int(get_user_age(user) or 0)
    except Exception:
        age = 0
    if is_teen_age(age_exact, age, user=user):
        return None
    if not is_adult_age(age_exact, age, user=user):
        return None

    log_date = log_date or user_today(user)
    subscription_data = check_subscription_or_response(user).data
    monetization = compute_monetization_flags(
        age,
        subscription_data,
        age_exact=age_exact,
        user=user,
    )
    conversion_enabled = bool(monetization.get("conversion_enabled"))

    posture_pts, nutrition_pts = _today_engine_points(user, log_date)
    today_daily_points = int(round(posture_pts + nutrition_pts))

    today_total_gain_cm = adult_daily_gains_cm_today(
        user, log_date, conversion_enabled=conversion_enabled
    )
    today_posture_plus_gain_cm = round(posture_pts * POINTS_TO_CM_ENGINE1, 4) if conversion_enabled else 0.0

    total_recovered_cm = live_cumulative_gain_cm(user)
    current_height_cm = live_height_cm(user)

    diagnostics = build_posture_optimization_diagnostics(user=user, optimization_breakdown=None)
    segments = {}
    for long_key, short_key in _SEGMENT_SHORT_KEYS.items():
        seg_payload = (diagnostics.get("segments") or {}).get(long_key) or {}
        opt = seg_payload.get("percent_optimized_precise", seg_payload.get("percent_optimized", 0))
        segments[short_key] = {
            "loss_cm": round(float(seg_payload.get("current_loss_cm", 0) or 0), 2),
            "opt_pct": round(float(opt or 0), 2),
        }

    today_daily_points = adult_engine1_points_today(user, log_date)
    if today_daily_points <= 0:
        today_daily_points = int(round(posture_pts + nutrition_pts))

    return {
        "today_daily_points": today_daily_points,
        "today_posture_plus_gain_cm": today_posture_plus_gain_cm,
        "today_total_gain_cm": today_total_gain_cm,
        "current_height_cm": current_height_cm,
        "total_recovered_cm": total_recovered_cm,
        "segments": segments,
    }
