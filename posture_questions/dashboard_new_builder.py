"""Build dashboard-new payload from /dashboard (get_posture_questions) base data."""
import logging

from users.models import HeightLedger
from utils.graph_age_projection import calculate_height_projection, floor_teen_projection_targets
from utils.paywall_flags import is_teen_age, user_profile_sex
from utils.posture.height_constants import normalize_sex
from utils.adult_dashboard_metrics import adult_chart_series, count_habits_logged
from utils.user_time import user_today
from utils.teen_dashboard_dots import (
    teen_lifestyle_nutrition_combined_percent,
)
from utils.combined_completion import combined_completion_for_user
from utils.posture.teen_genetic_average import (
    compute_daily_genetic_average_gain_cm,
    compute_genetic_average_cm,
)

logger = logging.getLogger(__name__)


def build_dashboard_new_from_payload(user, payload, *, include_debug=False):
    payload = dict(payload or {})
    age_exact = float(payload.get("age_exact") or 0.0)
    nav = payload.get("section16_navigation") or {}
    # Decimal age is canonical; do not treat 18yo as adult when account_tier is stale.
    profile_gender_early = normalize_sex((payload.get("profile") or {}).get("gender")) or user_profile_sex(user)
    if age_exact and is_teen_age(age_exact, gender=profile_gender_early, user=user):
        is_teen = True
    elif age_exact and not is_teen_age(age_exact, gender=profile_gender_early, user=user):
        is_teen = False
    else:
        _dv = nav.get("dashboard_variant")
        if _dv == "teen":
            is_teen = True
        elif _dv == "adult":
            is_teen = False
        else:
            is_teen = is_teen_age(age_exact, gender=profile_gender_early, user=user)

    scan_access = payload.get("scan_access") or {}
    section4 = payload.get("section4_contract") or {}
    section5 = payload.get("section5_contract") or {}
    growth_projection = payload.get("growth_projection") or {}
    diagnostics = payload.get("posture_optimization_diagnostics") or {}
    streaks = payload.get("streaks") or {}

    display_lines = section5.get("display_lines") or {}
    predictor_completed = bool(section5.get("predictor_completed") or display_lines.get("predictor_completed"))
    base_height_cm = float(section4.get("base_height_cm") or growth_projection.get("current_height_cm") or 0.0)
    teen_genetic_cumulative_cm = float(section5.get("genetic_cumulative_cm") or 0.0)
    teen_posture_cumulative_cm = float(section5.get("postureplus_cumulative_cm") or 0.0)
    # Section 5 formulas:
    # Blue line  = Base + Genetic_Cumulative
    # Red line   = Base + Genetic_Cumulative + PosturePlus_Cumulative
    teen_genetic_cm = round(base_height_cm + teen_genetic_cumulative_cm, 4)
    teen_growthmax_cm = round(base_height_cm + teen_genetic_cumulative_cm + teen_posture_cumulative_cm, 4)
    # Fallback to legacy display lines only if cumulatives are absent.
    if teen_genetic_cm <= 0 and display_lines.get("blue_genetic_line_cm") is not None:
        teen_genetic_cm = float(display_lines.get("blue_genetic_line_cm") or 0.0)
    if teen_growthmax_cm <= 0 and display_lines.get("red_us_optimized_line_cm") is not None:
        teen_growthmax_cm = float(display_lines.get("red_us_optimized_line_cm") or teen_genetic_cm)
    teen_true_optimized_cm = display_lines.get("green_true_optimized_cm")
    try:
        teen_true_optimized_cm = float(teen_true_optimized_cm) if teen_true_optimized_cm is not None else None
    except Exception:
        teen_true_optimized_cm = None
    teen_daily_gain_cm = float(section5.get("daily_gains_today_cm") or 0.0)
    # Section 5.3 / 16.2 readouts: Genetic+ and Posture+ (GrowthMax+ product name) cards are *today* deltas (cm),
    # not cumulative line heights (those stay in teen_lines_cm / live_metrics).
    teen_genetic_plus_today_cm = float(section5.get("genetic_plus_today_cm") or 0.0)
    teen_posture_plus_today_cm = float(section5.get("posture_plus_today_cm") or 0.0)
    # Teen live height follows cumulative formula (not projected lifetime target).
    teen_height_live_cm = float(teen_growthmax_cm or base_height_cm)
    teen_live_blue_cm = float(teen_genetic_cm or base_height_cm)
    teen_live_red_cm = float(teen_growthmax_cm or base_height_cm)

    adult_base_cm = float(base_height_cm)
    adult_recovered_cm = float(section4.get("recovered_so_far_cm") or 0.0)
    adult_daily_gain_cm = float(section4.get("daily_gains_cm") or 0.0)
    adult_height_live_cm = float(section4.get("height_live_cm") or adult_base_cm)

    top_cards = [
        {"key": "base_height", "label": "Base Height", "value_cm": round(adult_base_cm, 3)},
        {"key": "total_recovered", "label": "Total Recovered", "value_cm": round(adult_recovered_cm, 3)},
        {"key": "daily_gains", "label": "Daily Gains", "value_cm": round(adult_daily_gain_cm, 3)},
        {"key": "height", "label": "Height", "value_cm": round(adult_height_live_cm, 3)},
    ]

    segments = diagnostics.get("segments") or {}

    section4_posture = section4.get("posture_exercises") or {}
    section8 = payload.get("section8_mapping_summary") or {}
    teen_map = section8.get("teen_dashboard_mapping") or {}
    adult_map = section8.get("adult_dashboard_mapping") or {}
    teen_nutrition_dots = int(teen_map.get("teen_nutrition_dots") or 0)
    teen_lifestyle_dots = int(teen_map.get("teen_lifestyle_dots") or 0)
    # Section 5.10 — single formula for combined % (same as section8 teen_dashboard_mapping).
    teen_lifestyle_nutrition_pct = (
        teen_lifestyle_nutrition_combined_percent(teen_nutrition_dots, teen_lifestyle_dots)
        if is_teen
        else None
    )
    # Task 1 — daily optimization % (teen pool 68, adult pool 27).
    try:
        combined_completion = combined_completion_for_user(user, user_today(user), is_teen=is_teen)
    except Exception:
        logger.exception("combined_completion failed", extra={"user_id": getattr(user, "id", None)})
        combined_completion = None
    _pb_src = (teen_map if is_teen else adult_map).get("progress_bars_percent") or {}
    if isinstance(_pb_src, dict) and _pb_src:
        posture_bars = {str(k): int(v) for k, v in _pb_src.items()}
        # Always provide a precise (2-decimal) variant derived from the live segment math.
        # `progress_bars_percent` is legacy int-only mapping; UI can prefer the precise values.
        posture_bars_precise = {
            seg: float((seg_payload or {}).get("percent_optimized_precise", posture_bars.get(seg, 0)) or 0.0)
            for seg, seg_payload in segments.items()
        }
    else:
        posture_bars = {
            seg: int((seg_payload or {}).get("percent_optimized", 0) or 0)
            for seg, seg_payload in segments.items()
        }
        posture_bars_precise = {
            seg: float((seg_payload or {}).get("percent_optimized_precise", posture_bars.get(seg, 0)) or 0.0)
            for seg, seg_payload in segments.items()
        }
    today_streak = int(((streaks.get("health") or {}).get("current_streak") or 0))
    leaderboard = streaks.get("leaderboard") or {}
    # `get_user_leaderboard_rank()` returns `my_rank` / `total_rank` (not `rank`).
    rank_value = None
    if isinstance(leaderboard, dict):
        rank_value = leaderboard.get("my_rank", None)
        if rank_value is None:
            rank_value = leaderboard.get("total_rank", None)

    profile_gender = str((payload.get("profile") or {}).get("gender") or "male").strip().lower()
    if profile_gender not in {"male", "female"}:
        profile_gender = "male"
    from utils.paywall_flags import effective_full_access_trial_expired, effective_is_paid

    sub = payload.get("subscription") or {}
    paid = effective_is_paid(user, sub, age_exact=payload.get("age_exact"))
    trial_expired = effective_full_access_trial_expired(
        user, {**sub, "full_access_trial_expired": payload.get("full_access_trial_expired")},
        age_exact=payload.get("age_exact"),
    )
    teen_locked_post_day7 = bool(is_teen and not paid and trial_expired)
    # Spec (Sections 5.5 / 7.2 / 11.5): post-day-7 unpaid teen red line (and height card)
    # must flatline at the trial-end snapshot while blue continues to rise.
    if teen_locked_post_day7 and display_lines.get("red_us_optimized_line_cm") is not None:
        try:
            teen_live_red_cm = float(display_lines.get("red_us_optimized_line_cm") or teen_live_red_cm)
            teen_height_live_cm = float(teen_live_red_cm)
            teen_growthmax_cm = float(teen_live_red_cm)
        except Exception:
            logger.exception("Failed applying teen_locked_post_day7 red-line override")
    # Spec (Section 5.6 / 7.2): True Optimized Height is revealed ONLY when paid (not during trial).
    can_view_true_optimized = bool(is_teen and paid)
    teen_scan_required = bool(scan_access.get("teen_scan_required", False))
    true_optimized_locked = bool(
        display_lines.get("green_true_optimized_locked", False)
        or teen_locked_post_day7
        or (can_view_true_optimized and not predictor_completed)
    )
    teen_scan_completed = bool(scan_access.get("scan_completed"))
    anomalies = []
    # Build target metrics from growth projection (forecast model).
    try:
        teen_target_blue_cm = float(growth_projection.get("estimated_genetic_height_cm") or 0.0)
    except Exception:
        logger.exception("Failed parsing estimated_genetic_height_cm", extra={"value": repr(growth_projection.get("estimated_genetic_height_cm"))})
        teen_target_blue_cm = 0.0
    try:
        teen_target_red_cm = float(growth_projection.get("optimized_estimated_genetic_height_cm") or 0.0)
    except Exception:
        logger.exception("Failed parsing optimized_estimated_genetic_height_cm", extra={"value": repr(growth_projection.get("optimized_estimated_genetic_height_cm"))})
        teen_target_red_cm = 0.0
    if teen_target_blue_cm <= 0:
        teen_target_blue_cm = teen_live_blue_cm
    if teen_target_red_cm <= 0:
        teen_target_red_cm = teen_target_blue_cm
    # Target invariants: optimized (red) must not be below genetic (blue).
    teen_target_red_cm = max(teen_target_red_cm, teen_target_blue_cm)
    try:
        teen_target_unoptimized_cm = float(growth_projection.get("unoptimized_estimated_genetic_height_cm") or 0.0)
    except Exception:
        logger.exception("Failed parsing unoptimized_estimated_genetic_height_cm", extra={"value": repr(growth_projection.get("unoptimized_estimated_genetic_height_cm"))})
        teen_target_unoptimized_cm = 0.0
    if teen_target_unoptimized_cm <= 0:
        teen_target_unoptimized_cm = max(0.0, teen_target_blue_cm - 2.0)
    # Unoptimized must not exceed genetic target.
    teen_target_unoptimized_cm = min(teen_target_unoptimized_cm, teen_target_blue_cm)
    posture_boost_for_chart = max(0.0, teen_target_red_cm - teen_target_blue_cm)
    teen_target_blue_cm, teen_target_red_cm, teen_target_unoptimized_cm = floor_teen_projection_targets(
        max(teen_height_live_cm, base_height_cm),
        teen_target_blue_cm,
        teen_target_red_cm,
        teen_target_unoptimized_cm,
        posture_boost_cm=posture_boost_for_chart,
    )

    # Do not flag \"zero cumulative\" as anomalous unless we have actual ledger history.
    if (
        is_teen
        and teen_scan_completed
        and (HeightLedger.objects.filter(user=user, entry_type="daily_compute").exists())
        and teen_genetic_cumulative_cm <= 0
        and teen_posture_cumulative_cm <= 0
    ):
        anomalies.append("cumulative_zero_with_scan_completed")
    if is_teen and abs(teen_target_red_cm - teen_live_red_cm) > 5.0:
        anomalies.append("target_live_gap_large")
    if is_teen and teen_scan_required:
        anomalies.append("scan_required_pending_baseline")

    # Display mode:
    # - live: show Base+cum values
    # - target_projection_fallback: show projection lines if live cumulatives are missing/abnormal
    teen_display_mode = "live"
    if is_teen and teen_scan_required:
        teen_display_mode = "pending_scan_baseline"
    if is_teen and teen_scan_completed and "cumulative_zero_with_scan_completed" in anomalies and teen_target_red_cm > (teen_live_red_cm + 1.0):
        teen_display_mode = "target_projection_fallback"

    if is_teen and teen_display_mode == "target_projection_fallback":
        teen_card_genetic_cm = teen_target_blue_cm
        teen_card_growthmax_cm = teen_target_red_cm
        # Spec: the teen \"Height\" card is the current displayed height (live), not the target.
        teen_card_height_cm = teen_live_red_cm
    else:
        teen_card_genetic_cm = teen_live_blue_cm
        teen_card_growthmax_cm = teen_live_red_cm
        teen_card_height_cm = teen_live_red_cm
    local_today = user_today(user)
    teen_ga_cm = (
        round(float(compute_genetic_average_cm(user, local_today)), 4) if is_teen else None
    )
    teen_daily_ga_gain = (
        round(float(compute_daily_genetic_average_gain_cm(user, local_today)), 6)
        if is_teen
        else None
    )
    if is_teen:
        habits_logged_count = int(min(8, teen_nutrition_dots + teen_lifestyle_dots))
    else:
        habits_logged_count = count_habits_logged(user, local_today)

    if is_teen:
        top_cards = [
            {
                "key": "genetic_plus",
                "label": "Genetic +",
                "value_cm": round(teen_genetic_plus_today_cm, 3),
            },
            {
                "key": "posture_plus",
                "label": "Posture+",
                "value_cm": round(teen_posture_plus_today_cm, 3),
            },
            {"key": "daily_gains", "label": "Daily Gains", "value_cm": round(teen_daily_gain_cm, 3)},
            {"key": "height", "label": "Height", "value_cm": round(teen_card_height_cm, 3)},
        ]

    # Canonical teen line model for dashboard + chart:
    # blue = genetic line, red = us optimized, green = true optimized (paid/trial only).
    teen_chart_genetic_cm = teen_target_blue_cm if is_teen else teen_live_blue_cm
    teen_chart_optimized_cm = (
        teen_true_optimized_cm
        if (is_teen and teen_true_optimized_cm is not None and not true_optimized_locked)
        else teen_target_red_cm
    )
    teen_chart_unoptimized_cm = teen_target_unoptimized_cm
    canonical_chart = payload.get("chart_breakdown")
    adult_target_height_cm = float(section4.get("target_height_cm") or adult_height_live_cm or adult_base_cm)
    try:
        adult_estimated_genetic_cm = float(
            growth_projection.get("estimated_genetic_height_cm") or adult_base_cm
        )
    except Exception:
        adult_estimated_genetic_cm = float(adult_base_cm)
    adult_optimized_estimated_cm = float(max(adult_target_height_cm, adult_estimated_genetic_cm))
    # Spec adult dashboard does not use teen-style genetic projection comparisons.
    adult_unoptimized_cm = None
    adult_diff_cm = None
    adult_genetic_status = None
    if is_teen:
        try:
            canonical_chart = calculate_height_projection(
                teen_height_live_cm,
                teen_chart_optimized_cm,
                teen_chart_genetic_cm,
                teen_chart_unoptimized_cm,
                profile_gender,
                age_exact=age_exact,
            )
        except Exception:
            canonical_chart = payload.get("chart_breakdown")
    else:
        try:
            series = adult_chart_series(user, adult_target_height_cm)
            max_y = max(
                max(p["current_height_cm"] for p in series),
                max(p["target_height_cm"] for p in series),
            )
            canonical_chart = {
                "x_axis": "days",
                "series": series,
                "maxY": int(((max_y + 10) // 10) * 10),
            }
        except Exception:
            canonical_chart = payload.get("chart_breakdown")

    remaining_loss_cm = float(diagnostics.get("total_current_loss_cm") or 0.0)
    initial_recoverable_cm = float(diagnostics.get("total_recoverable_loss_cm") or remaining_loss_cm or 0.0)
    height_loss_box = {
        "label": "Height Lost to Posture",
        "remaining_cm": round(remaining_loss_cm, 2),
        "initial_recoverable_cm": round(initial_recoverable_cm, 2),
        "recovered": remaining_loss_cm <= 0.0,
        "sub_label": "Recoverable — shrinks as you train.",
    }

    dashboard = {
        "variant": "teen" if is_teen else "adult",
        "calculation_mode": teen_display_mode if is_teen else "adult_live",
        "anomalies": anomalies if is_teen else [],
        "genetic_average_cm": teen_ga_cm,
        "daily_genetic_average_gain_cm": teen_daily_ga_gain,
        "predictor_completed": predictor_completed if is_teen else None,
        "profile": {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            "age": (payload.get("profile") or {}).get("age"),
            "gender": (payload.get("profile") or {}).get("gender"),
            "base_height_cm": section4.get("base_height_cm"),
            "account_tier": payload.get("account_tier"),
        },
        "live_metrics": (
            {
                "base_height_cm": round(base_height_cm, 4),
                "genetic_blue_cm": round(teen_live_blue_cm, 4),
                "us_optimized_red_cm": round(teen_live_red_cm, 4),
                "height_cm": round(teen_live_red_cm, 4),
                "daily_gains_cm": round(teen_daily_gain_cm, 4),
                "genetic_cumulative_cm": round(teen_genetic_cumulative_cm, 4),
                "postureplus_cumulative_cm": round(teen_posture_cumulative_cm, 4),
            } if is_teen else {
                "base_height_cm": round(adult_base_cm, 4),
                "total_recovered_cm": round(adult_recovered_cm, 4),
                "daily_gains_cm": round(adult_daily_gain_cm, 4),
                "height_cm": round(adult_height_live_cm, 4),
            }
        ),
        "target_metrics": (
            {
                "genetic_blue_cm": round(teen_target_blue_cm, 4),
                "us_optimized_red_cm": round(teen_target_red_cm, 4),
                "unoptimized_cm": round(teen_target_unoptimized_cm, 4),
                "true_optimized_green_cm": (
                    round(teen_true_optimized_cm, 4) if (teen_true_optimized_cm is not None and not true_optimized_locked) else None
                ),
            } if is_teen else {
                "target_height_cm": section4.get("target_height_cm"),
            }
        ),
        "scan": {
            "scan_completed": bool(scan_access.get("scan_completed")),
            "can_scan": bool(scan_access.get("can_scan")) and (not teen_locked_post_day7),
            "scan_message": (
                "Unlock full Posture+, ultra-accurate True Optimized Height, and unlimited re-scans."
                if teen_locked_post_day7 else scan_access.get("scan_message")
            ),
            "rescan_timer_days": scan_access.get("Re_Scan_Timer"),
            "teen_scan_required": bool(scan_access.get("teen_scan_required", False)),
        },
        "top_graph": {
            "cards": top_cards,
            "teen_lines_cm": {
                # Spec (Section 16.2 teen): chart legend lines are the target endpoints,
                # not the live \"Height\" readout (which stays in cards/live_metrics).
                "genetic_blue": round(teen_target_blue_cm, 4),
                "us_optimized_red": round(teen_target_red_cm, 4),
                "true_optimized_green": (
                    round(teen_true_optimized_cm, 4) if (teen_true_optimized_cm is not None and not true_optimized_locked) else None
                ),
                "true_optimized_locked": true_optimized_locked,
            } if is_teen else None,
            "adult_target_height_cm": section4.get("target_height_cm") if not is_teen else None,
        },
        "routine_progress": {
            "cta": nav.get("primary_cta") or "Start Today's Routine",
            "posture_exercises_fraction": section4_posture.get("fraction_today"),
            "posture_exercises_done": int(section4_posture.get("completed_total_today") or 0),
            "posture_exercises_total": int(section4_posture.get("assigned_total") or 0),
            "exercises_done": int(section4_posture.get("completed_total_today") or 0),
            "total_exercises": int(section4_posture.get("assigned_total") or 0),
            "habits_logged": habits_logged_count,
            "posture_exercises_percent": (
                int(
                    round(
                        (
                            (int(section4_posture.get("completed_total_today") or 0) / max(1, int(section4_posture.get("assigned_total") or 0)))
                            * 100.0
                        )
                    )
                )
                if int(section4_posture.get("assigned_total") or 0) > 0
                else 0
            ),
            "nutrition_percent": (
                int(combined_completion["percent"])
                if combined_completion is not None
                else (
                    int(teen_lifestyle_nutrition_pct)
                    if is_teen
                    else int(section4.get("posture_nutrition_percent") or 0)
                )
            ),
            # Bug 11 — shared completion number that only hits 100% when BOTH lifestyle
            # (or adult nutrition) AND habits are fully done.
            "completion_percent": (
                int(combined_completion["percent"]) if combined_completion is not None else None
            ),
            "completion_breakdown": combined_completion,
            "teen_nutrition_dots": teen_nutrition_dots if is_teen else None,
            "teen_lifestyle_dots": teen_lifestyle_dots if is_teen else None,
            "streak_days": today_streak,
            "daily_points": int(payload.get("today_total_score") or 0),
            "daily_points_breakdown": payload.get("today_score_breakdown"),
            "rank": rank_value,
        },
        "posture_optimization": {
            "total_recoverable_loss_cm": diagnostics.get("total_recoverable_loss_cm"),
            "total_current_loss_cm": diagnostics.get("total_current_loss_cm"),
            "bars_percent": posture_bars,
            "bars_percent_precise": posture_bars_precise,
            "raw_segments": segments,
        },
        "height_loss_box": height_loss_box,
        "ai_analysis": payload.get("ai_analysis") or {},
        "chart_breakdown": canonical_chart,
        "subscription": payload.get("subscription") or {},
        "trial_data": {
            "is_teen": bool(is_teen),
            "is_trial": bool((payload.get("subscription") or {}).get("is_trial", False)),
            "trial_day": payload.get("trial_day"),
            "trial_start": (payload.get("subscription") or {}).get("trial_start"),
            "trial_end": (payload.get("subscription") or {}).get("trial_end"),
            "full_access_trial_active": bool(payload.get("full_access_trial_active")),
            "full_access_trial_expired": bool(payload.get("full_access_trial_expired")),
        },
        "important_data": {
            "growth_projection": {
                "current_height_cm": (
                    round(teen_live_red_cm, 4) if is_teen
                    else round(adult_height_live_cm, 4)
                ),
                "estimated_genetic_height_cm": (
                    round(teen_chart_genetic_cm, 4) if is_teen
                    else None
                ),
                "optimized_estimated_genetic_height_cm": (
                    round(teen_chart_optimized_cm, 4) if is_teen
                    else None
                ),
                "unoptimized_estimated_genetic_height_cm": (
                    round(teen_chart_unoptimized_cm, 4) if is_teen
                    else None
                ),
                "genetic_height_difference": (
                    round(teen_height_live_cm - teen_chart_genetic_cm, 4) if is_teen
                    else None
                ),
                "genetic_status": (
                    "equal_estimated_genetic_height" if is_teen and round(teen_height_live_cm - teen_chart_genetic_cm, 4) == 0
                    else (
                        "below_estimated_genetic_height" if is_teen and teen_height_live_cm < teen_chart_genetic_cm
                        else (
                            "above_estimated_genetic_height" if is_teen and teen_height_live_cm > teen_chart_genetic_cm
                            else None
                        )
                    )
                ),
            },
            "subscription": payload.get("subscription") or {},
            "response_data": (
                {
                    "tier": (payload.get("response_data") or {}).get("tier"),
                    "genetic_height_cm": round(teen_chart_genetic_cm, 4),
                    "current_height_cm": round(teen_height_live_cm, 4),
                    "optimized_height_cm": (
                        None if (teen_locked_post_day7 or (not can_view_true_optimized)) else round(teen_chart_optimized_cm, 4)
                    ),
                    "can_rescan": bool(scan_access.get("can_scan")) and (not teen_locked_post_day7),
                    "growth_max_active": bool(not true_optimized_locked),
                    "days_since_scan": scan_access.get("days_since_scan"),
                } if is_teen else {
                    "tier": (payload.get("response_data") or {}).get("tier", "adult"),
                    "current_height_cm": round(adult_height_live_cm, 4),
                    "target_height_cm": round(adult_target_height_cm, 4),
                    "height_reclaimed_cm": round(adult_recovered_cm, 4),
                    "remaining_cm": round(max(0.0, adult_target_height_cm - adult_height_live_cm), 4),
                    "can_rescan": bool(scan_access.get("can_scan")),
                    "ai_assistant": bool((payload.get("response_data") or {}).get("ai_assistant", True)),
                    "days_since_scan": scan_access.get("days_since_scan"),
                }
            ),
            "posture_source": payload.get("posture_source"),
            "last_scan": payload.get("last_scan"),
        },
        "meta": {
            "screen_state": (
                "dashboard_teen_locked_post_trial"
                if (is_teen and teen_locked_post_day7)
                else nav.get("current_screen_state")
            ),
            "age_exact": payload.get("age_exact"),
            "account_tier": payload.get("account_tier"),
            "trial_day": payload.get("trial_day"),
            "full_access_trial_active": payload.get("full_access_trial_active"),
            "full_access_trial_expired": payload.get("full_access_trial_expired"),
        },
    }

    if include_debug:
        dashboard["debug"] = {
            "section4_contract": section4,
            "section5_contract": section5,
            "scan_access": scan_access,
            "streaks": streaks,
        }


    return {
        "message": "Dashboard retrieved successfully",
        "dashboard": dashboard,
    }
