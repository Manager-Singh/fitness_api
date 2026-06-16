"""
Embed dashboard-new-shaped payload in log POST responses (workout-logs, nutra-logs).

Default: fast snapshot (targeted DB queries only).
Optional full rebuild via settings DASHBOARD_LOG_EMBED_FULL=True or request flag include_full_dashboard=1.
"""
import logging

from django.conf import settings

from utils.adult_dashboard_metrics import count_habits_logged

logger = logging.getLogger(__name__)

_SEGMENT_LONG_KEYS = {
    "spinal_compression": "spinal",
    "posture_collapse": "collapse",
    "pelvic_tilt_back": "pelvic",
    "leg_hamstring": "legs",
}


def _embed_unavailable(reason: str, **extra):
    out = {
        "message": "Dashboard unavailable",
        "dashboard": None,
        "dashboard_embed_error": reason,
    }
    out.update(extra)
    return out


def _strip_subscription_from_embed(payload):
    """Log POST embed: omit subscription/trial blobs (client uses GET /dashboard-new for those)."""
    if not isinstance(payload, dict):
        return payload
    dash = payload.get("dashboard")
    if not isinstance(dash, dict):
        return payload
    dash.pop("subscription", None)
    dash.pop("trial_data", None)
    important = dash.get("important_data")
    if isinstance(important, dict):
        important.pop("subscription", None)
    return payload


def _embed_daily_points(user, subscription_data=None) -> int:
    """Food + lifestyle activity + workouts + capped micro-habits (matches dashboard-new)."""
    from utils.check_payment import check_subscription_or_response
    from utils.scores_summary import get_today_daily_points

    sub = subscription_data if subscription_data is not None else check_subscription_or_response(user).data
    return int(get_today_daily_points(user, sub) or 0)


def _want_full_dashboard(request=None) -> bool:
    if bool(getattr(settings, "DASHBOARD_LOG_EMBED_FULL", False)):
        return True
    if request is None:
        return False
    try:
        if str(request.query_params.get("include_full_dashboard", "")).lower() in {"1", "true", "yes"}:
            return True
    except Exception:
        pass
    try:
        data = getattr(request, "data", None) or {}
        if str(data.get("include_full_dashboard", "")).lower() in {"1", "true", "yes"}:
            return True
    except Exception:
        pass
    return False


def _routine_progress_snapshot(user, log_date, *, is_teen: bool):
    from django.db.models import Count

    from users.models import DailyLog
    from workouts.models import RoutineType, UserRoutineExercise, WorkoutEntry

    daily = DailyLog.objects.filter(user=user, log_date=log_date).first()

    # Diet/hydration detail (calories, protein grams, hydration consumed) — same
    # source as /api/my-nutrition-plan so home + diary stay in sync.
    from nutration.food_macros import food_macros_from_entries, hydration_summary_for_user
    from nutration.models_log import NutraEntry as _NutraEntry

    _food_entries = _NutraEntry.objects.filter(
        session__user=user, session__date=log_date, food__isnull=False
    ).select_related("food")
    _macros = food_macros_from_entries(_food_entries)
    _hydration_today = hydration_summary_for_user(
        user, log_date, adult_nutrition_plan=not is_teen
    )

    if is_teen:
        from utils.teen_dashboard_dots import teen_lifestyle_dots_for_day, teen_nutrition_dots_from_food_points
        from nutration.models_log import NutraEntry
        from django.db.models import Sum

        assigned_total = UserRoutineExercise.objects.filter(
            routine__user=user,
            routine__is_active=True,
            routine__routine_type=RoutineType.POSTURE,
        ).count()
        completed_total = (
            WorkoutEntry.objects.filter(
                session__user=user,
                session__date=log_date,
                session__user_routine__routine_type=RoutineType.POSTURE,
                user_routine_exercise__isnull=False,
            )
            .values("user_routine_exercise_id")
            .distinct()
            .count()
        )
        raw_food = float(
            NutraEntry.objects.filter(session__user=user, session__date=log_date, food__isnull=False).aggregate(
                total=Sum("score")
            )["total"]
            or 0
        )
        nutrition_dots = teen_nutrition_dots_from_food_points(raw_food)
        lifestyle_dots = teen_lifestyle_dots_for_day(user, log_date)
        # Task 1 — daily optimization % (teen pool 68).
        from utils.combined_completion import teen_combined_completion

        combined = teen_combined_completion(user, log_date)
        nutrition_pct = int(combined["percent"])
        return {
            "cta": "Start Today's Routine",
            "posture_exercises_fraction": f"{completed_total}/{assigned_total or 0}",
            "posture_exercises_done": completed_total,
            "posture_exercises_total": assigned_total,
            "exercises_done": completed_total,
            "total_exercises": assigned_total,
            "habits_logged": int(min(8, nutrition_dots + lifestyle_dots)),
            "posture_exercises_percent": int(round((completed_total / max(1, assigned_total)) * 100)),
            "nutrition_percent": nutrition_pct,
            "completion_percent": nutrition_pct,
            "completion_breakdown": combined,
            "teen_nutrition_dots": nutrition_dots,
            "teen_lifestyle_dots": lifestyle_dots,
            "today_total_calories": _macros["today_total_calories"],
            "today_total_protein": _macros["today_total_protein"],
            "hydration_today": _hydration_today,
            "streak_days": 0,
            "daily_points": _embed_daily_points(user, subscription_data=None),
            "rank": None,
        }

    assigned_total = UserRoutineExercise.objects.filter(
        routine__user=user,
        routine__is_active=True,
        routine__routine_type=RoutineType.POSTURE,
    ).count()
    completed_total = (
        WorkoutEntry.objects.filter(
            session__user=user,
            session__date=log_date,
            session__user_routine__routine_type=RoutineType.POSTURE,
            user_routine_exercise__isnull=False,
        )
        .values("user_routine_exercise_id")
        .distinct()
        .count()
    )
    # Part 2 — adult nutrition is now protein + hydration points (13-food list retired).
    from utils.adult_nutrition import adult_nutrition_points_today

    adult_nutrition_pts = int(adult_nutrition_points_today(user, log_date))
    # Task 1 — daily optimization % (adult pool 27).
    from utils.combined_completion import adult_combined_completion

    combined = adult_combined_completion(user, log_date)
    nutrition_pct = int(combined["percent"])
    return {
        "cta": "Start Today's Routine",
        "posture_exercises_fraction": f"{completed_total}/{assigned_total or 0}",
        "posture_exercises_done": completed_total,
        "posture_exercises_total": assigned_total,
        "exercises_done": completed_total,
        "total_exercises": assigned_total,
        "habits_logged": count_habits_logged(user, log_date),
        "nutrition_points": adult_nutrition_pts,
        "nutrition_traceable_points": adult_nutrition_pts,
        "posture_exercises_percent": int(round((completed_total / max(1, assigned_total)) * 100)),
        "nutrition_percent": int(nutrition_pct),
        "completion_percent": int(nutrition_pct),
        "completion_breakdown": combined,
        "teen_nutrition_dots": None,
        "teen_lifestyle_dots": None,
        "today_total_calories": _macros["today_total_calories"],
        "today_total_protein": _macros["today_total_protein"],
        "hydration_today": _hydration_today,
        "streak_days": 0,
        "daily_points": _embed_daily_points(user, subscription_data=None),
        "rank": None,
    }


def _posture_optimization_from_diagnostics(diagnostics: dict) -> dict:
    segments = diagnostics.get("segments") or {}
    bars_percent = {
        str(seg): int((payload or {}).get("percent_optimized", 0) or 0)
        for seg, payload in segments.items()
    }
    bars_percent_precise = {
        str(seg): float((payload or {}).get("percent_optimized_precise", bars_percent.get(seg, 0)) or 0)
        for seg, payload in segments.items()
    }
    return {
        "total_recoverable_loss_cm": diagnostics.get("total_recoverable_loss_cm"),
        "total_current_loss_cm": diagnostics.get("total_current_loss_cm"),
        "bars_percent": bars_percent,
        "bars_percent_precise": bars_percent_precise,
        "raw_segments": segments,
    }


def _build_dashboard_new_embed_fast(user, log_date):
    """Lightweight dashboard-new snapshot for log POST (no full /dashboard rebuild)."""
    from utils.adult_dashboard_live import build_adult_dashboard_live_payload
    from utils.adult_dashboard_metrics import adult_base_height_cm
    from utils.age import get_user_age, get_user_age_exact
    from utils.posture.diagnostics_contract import build_posture_optimization_diagnostics
    from users.spec_runtime import get_user_runtime_state_snapshot

    try:
        age_exact = float(get_user_age_exact(user) or 0)
    except Exception:
        age_exact = 0.0
    from utils.paywall_flags import is_teen_age

    is_teen = is_teen_age(age_exact, user=user)

    diagnostics = build_posture_optimization_diagnostics(user=user, optimization_breakdown=None)
    routine_progress = _routine_progress_snapshot(user, log_date, is_teen=is_teen)

    if is_teen:
        from utils.log_embed_metrics import teen_today_dashboard_metrics, teen_top_cards_from_metrics

        metrics = teen_today_dashboard_metrics(user, log_date)
        live_metrics = {
            "base_height_cm": metrics["base_height_cm"],
            "genetic_blue_cm": metrics["genetic_blue_cm"],
            "us_optimized_red_cm": metrics["us_optimized_red_cm"],
            "height_cm": metrics["height_cm"],
            "daily_gains_cm": metrics["daily_gains_cm"],
            "genetic_cumulative_cm": metrics["genetic_cumulative_cm"],
            "postureplus_cumulative_cm": metrics["postureplus_cumulative_cm"],
        }
        top_cards = teen_top_cards_from_metrics(metrics)
        return {
            "message": "Dashboard retrieved successfully",
            "dashboard": {
                "variant": "teen",
                "calculation_mode": "live",
                "anomalies": [],
                "live_metrics": live_metrics,
                "target_metrics": {},
                "top_graph": {"cards": top_cards, "teen_lines_cm": None},
                "routine_progress": routine_progress,
                "posture_optimization": _posture_optimization_from_diagnostics(diagnostics),
            },
        }

    live = build_adult_dashboard_live_payload(user, log_date)
    if not live:
        return _embed_unavailable("adult_live_payload_failed")

    base_cm = adult_base_height_cm(user)
    runtime = get_user_runtime_state_snapshot(user) or {}
    target_cm = round(
        base_cm + float(int(runtime.get("total_recoverable_loss_um") or 0)) / 10000.0,
        4,
    )
    live_metrics = {
        "base_height_cm": round(base_cm, 4),
        "total_recovered_cm": live["total_recovered_cm"],
        "daily_gains_cm": live["today_total_gain_cm"],
        "height_cm": live["current_height_cm"],
    }
    top_cards = [
        {"key": "base_height", "label": "Base Height", "value_cm": round(base_cm, 3)},
        {"key": "total_recovered", "label": "Total Recovered", "value_cm": round(live["total_recovered_cm"], 3)},
        {"key": "daily_gains", "label": "Daily Gains", "value_cm": round(live["today_total_gain_cm"], 3)},
        {"key": "height", "label": "Height", "value_cm": round(live["current_height_cm"], 3)},
    ]
    routine_progress["daily_points"] = live["today_daily_points"]

    return {
        "message": "Dashboard retrieved successfully",
        "dashboard": {
            "variant": "adult",
            "calculation_mode": "adult_live",
            "anomalies": [],
            "live_metrics": live_metrics,
            "target_metrics": {"target_height_cm": target_cm},
            "top_graph": {"cards": top_cards, "teen_lines_cm": None, "adult_target_height_cm": target_cm},
            "routine_progress": routine_progress,
            "posture_optimization": _posture_optimization_from_diagnostics(diagnostics),
        },
    }


def _build_dashboard_new_embed_full(user, log_date, include_debug=False):
    """Full /dashboard-new rebuild (slow — use only when explicitly requested)."""
    from utils.user_time import user_today
    from posture_questions.views import DashboardBaseUnavailable, build_dashboard_base_payload
    from posture_questions.dashboard_new_builder import build_dashboard_new_from_payload
    from posture_questions.serializers_dashboard import DashboardNewResponseSerializer

    log_date = log_date or user_today(user)

    try:
        base_payload = build_dashboard_base_payload(user)
    except DashboardBaseUnavailable:
        logger.info(
            "dashboard_new_embed full: subscription blocked, using fast snapshot",
            extra={"user_id": getattr(user, "id", None)},
        )
        return _build_dashboard_new_embed_fast(user, log_date)
    except Exception:
        logger.exception("dashboard_new_embed full: base payload failed", extra={"user_id": getattr(user, "id", None)})
        return _embed_unavailable("dashboard_base_failed")

    try:
        response_payload = build_dashboard_new_from_payload(user, base_payload, include_debug=include_debug)
        serializer = DashboardNewResponseSerializer(data=response_payload)
        serializer.is_valid(raise_exception=True)
        return dict(serializer.validated_data)
    except Exception:
        logger.exception("dashboard_new_embed full: build failed", extra={"user_id": getattr(user, "id", None)})
        return _embed_unavailable("dashboard_new_build_failed")


def build_dashboard_new_embed(user, log_date=None, include_debug=False, request=None):
    """
    Dashboard-new payload for log responses. Fast by default.
    Omits subscription/trial_data (use GET /api/dashboard-new for billing state).
    """
    from utils.user_time import user_today

    log_date = log_date or user_today(user)
    if _want_full_dashboard(request):
        payload = _build_dashboard_new_embed_full(user, log_date, include_debug=include_debug)
    else:
        payload = _build_dashboard_new_embed_fast(user, log_date)
    return _strip_subscription_from_embed(payload)
