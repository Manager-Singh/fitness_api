from datetime import date

from django.utils import timezone
from django.db.models import Sum

from posture.models import PostureReport
from nutration.models_log import NutraEntry
from user_profile.models import UserProfile
from workouts.models import WorkoutEntry
from users.models import DailyLog, HeightLedger, PostureState, User
from utils.age import get_user_age_exact_on_date, get_user_age_on_date
from utils.check_payment import check_subscription_or_response
from utils.posture.height_constants import (
    OPTIMIZATION_GAP_CM,
    POINTS_TO_CM_ENGINE1,
    POINTS_TO_CM_ENGINE2,
    POSTURE_SEGMENT_DISTRIBUTION_RATIO,
)
from utils.user_time import user_today

import logging

logger = logging.getLogger(__name__)


def _to_um(cm_value):
    try:
        return int(round(float(cm_value) * 10000.0))
    except Exception:
        logger.exception("_to_um failed", extra={"cm_value": repr(cm_value)})
        return 0


def _to_dm_from_engine2_points(engine2_points):
    """
    Spec v3.2 (Section 13.4 / 14.1):
    - Engine 2: 1 point = 0.00005 cm = 0.5 μm = 5 dμm (0.1 μm units)
    Store as integer dμm to preserve half-micron precision.
    """
    try:
        return int(round(float(engine2_points or 0) * 5.0))
    except Exception:
        logger.exception("_to_dm_from_engine2_points failed", extra={"engine2_points": repr(engine2_points)})
        return 0


def _um_from_dm(dm_value):
    """Convert deci-micrometers (0.1 μm) → rounded integer μm."""
    try:
        return int(round(float(dm_value or 0) / 10.0))
    except Exception:
        logger.exception("_um_from_dm failed", extra={"dm_value": repr(dm_value)})
        return 0


def _sum_prior_engine_deltas(user):
    """
    Fast path for Section 14.1 cumulative re-derivation.

    Prefer atomic columns when present; fall back to metadata for older rows.
    """
    qs = HeightLedger.objects.filter(user=user, entry_type="daily_compute")
    agg = qs.aggregate(
        e1_um=Sum("engine1_delta_um"),
        bio_um=Sum("bio_delta_um"),
        e2_dm=Sum("engine2_delta_dm"),
    )
    prior_engine1_um = int(agg.get("e1_um") or 0)
    prior_bio_um = int(agg.get("bio_um") or 0)
    prior_engine2_dm = int(agg.get("e2_dm") or 0)

    # Backward compatibility: if we have history but totals are zero, older rows may
    # still only have JSON metadata populated. Recompute from JSON in that case.
    if (prior_engine1_um == 0 and prior_bio_um == 0 and prior_engine2_dm == 0) and qs.exists():
        prior_engine1_um = 0
        prior_bio_um = 0
        prior_engine2_dm = 0
        for row in qs.only("metadata", "engine2_delta_dm").iterator(chunk_size=500):
            md = row.metadata or {}
            try:
                prior_engine1_um += int(md.get("engine1_delta_um", 0) or 0)
            except Exception:
                logger.exception(
                    "Failed reading engine1_delta_um from metadata",
                    extra={"row_id": getattr(row, "id", None)},
                )
            try:
                prior_bio_um += int(md.get("bio_delta_um", 0) or 0)
            except Exception:
                logger.exception(
                    "Failed reading bio_delta_um from metadata",
                    extra={"row_id": getattr(row, "id", None)},
                )
            try:
                prior_engine2_dm += int(getattr(row, "engine2_delta_dm", 0) or 0) or int(
                    md.get("engine2_delta_dm", 0) or 0
                )
            except Exception:
                logger.exception(
                    "Failed reading engine2_delta_dm from ledger row",
                    extra={"row_id": getattr(row, "id", None)},
                )

    return prior_engine1_um, prior_bio_um, prior_engine2_dm


def _get_or_create_state(user):
    state, _ = PostureState.objects.get_or_create(user=user)
    latest_report = PostureReport.objects.filter(user=user).order_by("-created_at").first()
    if latest_report and not state.scan_completed:
        state.scan_completed = True
        profile = UserProfile.objects.filter(user=user).first()
        state.last_scan_at = getattr(profile, "last_scan", None)

    # Backfill recoverable/current loss values from latest report if not yet populated.
    if latest_report and state.total_recoverable_loss_um <= 0:
        try:
            data = latest_report.data or {}
            breakdown = data.get("optimization_breakdown") or {}
            seg_map = {
                "spinal_compression": "spinal_current_loss_um",
                "posture_collapse": "collapse_current_loss_um",
                "pelvic_tilt_back": "pelvic_current_loss_um",
                "leg_hamstring": "legs_current_loss_um",
            }
            total = 0.0
            for seg, field in seg_map.items():
                seg_data = breakdown.get(seg) or {}
                cur = float(seg_data.get("current_loss_cm", 0) or 0)
                setattr(state, field, _to_um(cur))
                total += max(0.0, cur)
            # If explicit recoverable value is present, prefer it.
            explicit = data.get("total_recoverable_loss_cm")
            if explicit is not None:
                total = float(explicit or 0)
            state.total_recoverable_loss_um = _to_um(total)
        except Exception:
            logger.exception("_get_or_create_state: failed backfill from latest_report", extra={"user_id": getattr(user, "id", None)})

    state.save()
    return state


def set_daily_validated(user, log_date):
    """
    Docx Section 13.5 set_daily_validated():
    - Adult: all Core posture complete AND >=1 food in each required category.
    - Teen: all Core posture complete AND all Core HGH complete AND >=1 food logged.
    """
    from workouts.models import RoutineType, Tier as RoutineTier
    from nutration.models_log import NutraEntry
    from workouts.models import WorkoutEntry
    from users.models import DailyLog

    daily, _ = DailyLog.objects.get_or_create(user=user, log_date=log_date)
    try:
        age = int(get_user_age_on_date(user, log_date) or 0)
    except Exception:
        logger.exception(
            "set_daily_validated: age parse failed",
            extra={"log_date": str(log_date), "user_id": getattr(user, "id", None)},
        )
        age = 0

    def _core_done(routine_type):
        assigned = set(
            WorkoutEntry.objects.filter(
                session__user=user,
                session__date=log_date,
                session__user_routine__routine_type=routine_type,
                user_routine_exercise__tier=RoutineTier.CORE,
            ).values_list("user_routine_exercise_id", flat=True)
        )
        required = set(
            WorkoutEntry.objects.filter(
                session__user=user,
                session__date=log_date,
                session__user_routine__routine_type=routine_type,
            )
            .values_list("user_routine_exercise_id", flat=True)
        )
        # If no explicit routine-exercise IDs exist, fall back to "any core logged" safeguard.
        if not required:
            return False
        return required.issubset(assigned)

    if age >= 21:
        core_posture_done = _core_done(RoutineType.POSTURE)
        foods = NutraEntry.objects.filter(
            session__user=user,
            session__date=log_date,
            food__isnull=False,
        ).select_related("module")
        has_disc = False
        has_muscle = False
        for e in foods:
            module = getattr(e, "module", None)
            cat = str(getattr(module, "nutrition_category", "") or "").lower()
            if cat == "disc":
                has_disc = True
            elif cat == "muscle":
                has_muscle = True
            else:
                # Backward compatible fallback for older DB rows.
                module_name = str(getattr(module, "name", "") or "").lower()
                if any(t in module_name for t in ("disc", "lubric", "spine")):
                    has_disc = True
                if any(t in module_name for t in ("muscle", "repair", "fuel")):
                    has_muscle = True
        daily.validated = bool(core_posture_done and has_disc and has_muscle)
    else:
        core_posture_done = _core_done(RoutineType.POSTURE)
        core_hgh_done = _core_done(RoutineType.HGH)
        any_food = NutraEntry.objects.filter(
            session__user=user,
            session__date=log_date,
            food__isnull=False,
        ).exists()
        daily.validated = bool(core_posture_done and core_hgh_done and any_food)

    daily.save(update_fields=["validated", "updated_at"])
    return daily


def _redistribute_engine1_gain_across_segments(state, engine1_gain_um):
    """
    Section 4.3 redistribution:
    - Apply posture gain only to active segments (Current_Loss > 0)
    - Re-normalize segment weights as segments get fully recovered.
    """
    gain_um = max(0, int(engine1_gain_um or 0))
    if gain_um <= 0:
        return

    seg_defs = [
        ("spinal_compression", "spinal_current_loss_um"),
        ("posture_collapse", "collapse_current_loss_um"),
        ("pelvic_tilt_back", "pelvic_current_loss_um"),
        ("leg_hamstring", "legs_current_loss_um"),
    ]
    active = []
    for key, field in seg_defs:
        cur = max(0, int(getattr(state, field, 0) or 0))
        if cur > 0:
            active.append((key, field, cur))
    if not active:
        return

    total_weight = sum(float(POSTURE_SEGMENT_DISTRIBUTION_RATIO.get(k, 0.0) or 0.0) for k, _, _ in active)
    if total_weight <= 0:
        return

    consumed = 0
    for idx, (key, field, cur) in enumerate(active):
        weight = float(POSTURE_SEGMENT_DISTRIBUTION_RATIO.get(key, 0.0) or 0.0)
        if idx == len(active) - 1:
            share = max(0, gain_um - consumed)
        else:
            share = int(round(gain_um * (weight / total_weight)))
            consumed += share
        setattr(state, field, max(0, cur - share))

    state.save(
        update_fields=[
            "spinal_current_loss_um",
            "collapse_current_loss_um",
            "pelvic_current_loss_um",
            "legs_current_loss_um",
            "updated_at",
        ]
    )


def _reset_adult_posture_segments_from_latest_scan(user):
    """
    Restore PostureState segment losses from the latest scan report (Section 4.3 baseline).
    Used before replaying adult engine1 history during Section 14.2 rebuilds.
    """
    state, _ = PostureState.objects.get_or_create(user=user)
    latest_report = PostureReport.objects.filter(user=user).order_by("-created_at").first()
    if not latest_report:
        state.save()
        return state
    try:
        data = latest_report.data or {}
        breakdown = data.get("optimization_breakdown") or {}
        seg_map = {
            "spinal_compression": "spinal_current_loss_um",
            "posture_collapse": "collapse_current_loss_um",
            "pelvic_tilt_back": "pelvic_current_loss_um",
            "leg_hamstring": "legs_current_loss_um",
        }
        total = 0.0
        for seg, field in seg_map.items():
            seg_data = breakdown.get(seg) or {}
            cur = float(seg_data.get("current_loss_cm", 0) or 0)
            setattr(state, field, _to_um(cur))
            total += max(0.0, cur)
        explicit = data.get("total_recoverable_loss_cm")
        if explicit is not None:
            total = float(explicit or 0)
        state.total_recoverable_loss_um = _to_um(total)
    except Exception:
        logger.exception("_reset_adult_posture_segments_from_latest_scan failed", extra={"user_id": getattr(user, "id", None)})
    state.save(
        update_fields=[
            "spinal_current_loss_um",
            "collapse_current_loss_um",
            "pelvic_current_loss_um",
            "legs_current_loss_um",
            "total_recoverable_loss_um",
            "updated_at",
        ]
    )
    return state


def _replay_adult_engine1_ledger_before(user, before_log_date, state):
    """Apply adult-only historical engine1 ledger rows onto posture state (Section 14.2)."""
    if not state:
        return
    qs = HeightLedger.objects.filter(
        user=user,
        log_date__lt=before_log_date,
        entry_type="daily_compute",
    ).order_by("log_date", "created_at")
    for row in qs:
        try:
            row_age = int(get_user_age_on_date(user, row.log_date) or 0)
        except Exception:
            logger.exception(
                "_replay_adult_engine1_ledger_before: age parse failed",
                extra={"row_id": getattr(row, "id", None), "log_date": str(getattr(row, "log_date", ""))},
            )
            row_age = 0
        if row_age < 21:
            continue
        try:
            e1 = int((row.metadata or {}).get("engine1_delta_um", 0) or 0)
        except Exception:
            logger.exception(
                "_replay_adult_engine1_ledger_before: engine1_delta_um parse failed",
                extra={"row_id": getattr(row, "id", None)},
            )
            e1 = 0
        _redistribute_engine1_gain_across_segments(state, e1)


def _needs_adult_posture_replay_for_rebuild(user, from_date):
    """True if any pre-window daily_compute used adult (21+) engine1 redistribution."""
    try:
        if int(get_user_age_on_date(user, from_date) or 0) >= 21:
            return True
    except Exception:
        logger.exception(
            "_needs_adult_posture_replay_for_rebuild: age parse failed",
            extra={"from_date": str(from_date), "user_id": getattr(user, "id", None)},
        )
    prior_dates = (
        HeightLedger.objects.filter(
            user=user,
            log_date__lt=from_date,
            entry_type="daily_compute",
        )
        .values_list("log_date", flat=True)
        .distinct()
    )
    for d in prior_dates:
        try:
            if int(get_user_age_on_date(user, d) or 0) >= 21:
                return True
        except Exception:
            logger.exception(
                "_needs_adult_posture_replay_for_rebuild: age parse failed",
                extra={"date": str(d), "user_id": getattr(user, "id", None)},
            )
            continue
    return False


def rebuild_ledger_from_date(user, from_date):
    """
    Section 14.2 rebuildLedgerFromDate:
    delete ledger rows from ``from_date`` onward, restore adult posture baseline + replay
    adult engine1 through the day before ``from_date``, then recompute each affected day.
    """
    HeightLedger.objects.filter(user=user, log_date__gte=from_date).delete()

    state = None
    if _needs_adult_posture_replay_for_rebuild(user, from_date):
        state = _reset_adult_posture_segments_from_latest_scan(user)
        _replay_adult_engine1_ledger_before(user, from_date, state)

    # Primary source is DailyLog, but seeded/test data may create Workout/Nutra rows
    # without creating DailyLog rows for every date. Always union all candidate days.
    dailylog_days = list(
        DailyLog.objects.filter(user=user, log_date__gte=from_date)
        .values_list("log_date", flat=True)
        .distinct()
    )
    from nutration.models_log import NutraEntry
    from workouts.models import WorkoutEntry

    workout_days = list(
        WorkoutEntry.objects.filter(session__user=user, session__date__gte=from_date)
        .values_list("session__date", flat=True)
        .distinct()
    )
    nutra_days = list(
        NutraEntry.objects.filter(session__user=user, session__date__gte=from_date)
        .values_list("session__date", flat=True)
        .distinct()
    )
    days = sorted({*dailylog_days, *workout_days, *nutra_days})
    results = []
    for d in days:
        results.append(compute_daily_height_for_user(user, log_date=d, force_recompute=True))
    return {
        "user_id": user.id,
        "from_date": str(from_date),
        "days_rebuilt": len(results),
        "results": results,
    }


def _interpolated_teen_bio_gain_cm(user, base_height_cm, on_date=None):
    """
    Section 5.1: DOB-based linear interpolation biological gain.
    """
    on_date = on_date or date.today()
    age_exact = get_user_age_exact_on_date(user, on_date)
    if age_exact is None:
        return 0.0
    age_floor = int(age_exact)
    age_frac = max(0.0, age_exact - age_floor)

    # Annual rates by birthday bracket (13->14 ... 20->21)
    male_rates = {13: 3.60, 14: 2.60, 15: 1.90, 16: 1.55, 17: 1.10, 18: 0.75, 19: 0.30, 20: 0.20}
    female_rates = {13: 2.25, 14: 1.25, 15: 0.40, 16: 0.10, 17: 0.0, 18: 0.0, 19: 0.0, 20: 0.0}
    profile = UserProfile.objects.filter(user=user).first()
    sex = str(getattr(profile, "gender", "") or "").strip().lower()

    if sex == "female" and age_exact >= 17.0:
        return 0.0

    rates = female_rates if sex == "female" else male_rates
    rate_now = float(rates.get(age_floor, 0.0))
    rate_next = float(rates.get(age_floor + 1, 0.0))
    interp_rate = rate_now + age_frac * (rate_next - rate_now)
    if interp_rate <= 0:
        return 0.0
    return max(0.0, float(base_height_cm) * (interp_rate / 100.0) / 365.0)


def _daily_engine_points(user, log_date, age, subscription_data):
    """
    Section 11 routing/caps on current day data.
    Returns (engine1_points, engine2_points, exercise_points, food_points, lifestyle_points)
    """
    workout_qs = WorkoutEntry.objects.filter(session__user=user, session__date=log_date).select_related(
        "session__user_routine"
    )
    posture_pts = 0.0
    hgh_pts = 0.0
    hgh_exercise_counts = {}
    for w in workout_qs:
        session = getattr(w, "session", None)
        user_routine = getattr(session, "user_routine", None)
        rt = str(getattr(user_routine, "routine_type", "") or "").lower()
        pts = float(w.points or 0)
        if rt == "hgh":
            ex_id = int(getattr(w, "exercise_id", 0) or 0)
            hgh_exercise_counts[ex_id] = hgh_exercise_counts.get(ex_id, 0) + 1
            if hgh_exercise_counts[ex_id] > 2:
                # Section 11.3 per-exercise teen HGH spam guard.
                continue
            hgh_pts += pts
        else:
            posture_pts += pts

    nutra_qs = NutraEntry.objects.filter(session__user=user, session__date=log_date).select_related("module")
    food_pts = 0.0
    adult_disc_scores = []
    adult_muscle_scores = []
    sleep_pts = 0.0
    sun_pts = 0.0
    med_pts = 0.0
    hyd_pts = 0.0
    for n in nutra_qs:
        pts = float(n.score or 0)
        module = getattr(n, "module", None)
        module_name = str(getattr(module, "name", "") or "").lower()
        module_cat = str(getattr(module, "nutrition_category", "") or "").lower()
        if n.food_id:
            food_pts += pts
            if age >= 21:
                if module_cat == "disc" or any(token in module_name for token in ("disc", "lubric", "spine")):
                    adult_disc_scores.append(pts)
                elif module_cat == "muscle" or any(token in module_name for token in ("muscle", "repair", "fuel")):
                    adult_muscle_scores.append(pts)
            continue
        if "sleep" in module_name:
            sleep_pts += pts
        elif "sun" in module_name:
            sun_pts += pts
        elif "meditat" in module_name:
            med_pts += pts
        elif ("hydrat" in module_name) or ("water" in module_name):
            hyd_pts += pts

    exercise_points = int(round(posture_pts + hgh_pts))
    lifestyle_points = int(round(sleep_pts + sun_pts + med_pts + hyd_pts))
    food_points = int(round(food_pts))

    if age >= 21:
        # Section 4.1/11.3 adult nutrition math:
        # only top 2 disc + top 2 muscle foods count toward engine.
        valid_food_scores = sorted(adult_disc_scores, reverse=True)[:2] + sorted(adult_muscle_scores, reverse=True)[:2]
        nutrition_for_engine = min(sum(valid_food_scores), 12.0) if posture_pts > 0 else 0.0
        return posture_pts + nutrition_for_engine, 0.0, exercise_points, food_points, lifestyle_points

    trial_day = subscription_data.get("trial_day")
    is_paid = bool(subscription_data.get("is_paid", False))
    is_trial = bool(subscription_data.get("is_trial", False))
    trial_expired_unpaid = bool((not is_paid) and (not is_trial) and trial_day is not None and int(trial_day) > 7)

    if trial_expired_unpaid:
        return 0.0, 0.0, exercise_points, food_points, lifestyle_points

    engine1 = posture_pts
    if exercise_points <= 0:
        # Zero-log day: lifestyle still eligible for engine2.
        engine2 = min(sleep_pts, 10.0) + min(sun_pts, 6.0) + min(med_pts, 2.0) + min(hyd_pts, 1.0)
        return engine1, engine2, exercise_points, food_points, lifestyle_points

    engine2 = (
        min(hgh_pts, 30.0)
        + min(food_pts, 35.0)
        + min(sleep_pts, 10.0)
        + min(sun_pts, 6.0)
        + min(med_pts, 2.0)
        + min(hyd_pts, 1.0)
    )
    return engine1, engine2, exercise_points, food_points, lifestyle_points


def compute_daily_height_for_user(user, log_date=None, force_recompute=False):
    log_date = log_date or user_today(user)
    state = _get_or_create_state(user)
    existing = HeightLedger.objects.filter(
        user=user,
        log_date=log_date,
        entry_type="daily_compute",
    ).order_by("-created_at").first()
    if existing and not force_recompute:
        return {
            "user_id": user.id,
            "delta_um": int(existing.delta_um or 0),
            "cumulative_um": int(existing.cumulative_um or 0),
            "skipped": True,
        }
    if force_recompute:
        HeightLedger.objects.filter(
            user=user,
            log_date=log_date,
            entry_type="daily_compute",
        ).delete()

    try:
        age = int(get_user_age_on_date(user, log_date) or 0)
    except Exception:
        logger.exception(
            "compute_daily_height_for_user: age parse failed",
            extra={"log_date": str(log_date), "user_id": getattr(user, "id", None)},
        )
        age = 0

    subscription_data = check_subscription_or_response(user).data
    e1, e2, exercise_points, food_points, lifestyle_points = _daily_engine_points(
        user=user,
        log_date=log_date,
        age=age,
        subscription_data=subscription_data,
    )

    daily, _ = DailyLog.objects.get_or_create(user=user, log_date=log_date)
    daily.exercise_points = exercise_points
    daily.food_points = food_points
    daily.lifestyle_points = lifestyle_points
    daily.engine1_points = int(round(float(e1)))
    daily.engine2_points = int(round(float(e2)))
    daily.save()
    # Strict spec validation for streak/leaderboard correctness.
    set_daily_validated(user, log_date)

    # Section 11 formulas and routing.
    engine1_delta_um = _to_um(e1 * POINTS_TO_CM_ENGINE1)
    # Engine2 must preserve 0.5 μm increments: store as dμm, derive μm only for legacy totals.
    engine2_delta_dm = _to_dm_from_engine2_points(e2)
    engine2_delta_um = _um_from_dm(engine2_delta_dm)
    bio_delta_um = 0

    if 13 <= age <= 20:
        profile = UserProfile.objects.filter(user=user).first()
        base_height_cm = float(getattr(profile, "base_height_cm", None) or getattr(profile, "current_height_cm", 0) or 0)
        bio_delta_um = _to_um(_interpolated_teen_bio_gain_cm(user, base_height_cm, on_date=log_date))
        prior_engine1_um = 0
        prior_rows = HeightLedger.objects.filter(user=user, entry_type="daily_compute")
        for row in prior_rows:
            try:
                prior_engine1_um += int((row.metadata or {}).get("engine1_delta_um", 0))
            except Exception:
                logger.exception(
                    "compute_daily_height_for_user: failed reading engine1_delta_um from metadata",
                    extra={"row_id": getattr(row, "id", None)},
                )
        teen_engine1_cap_um = _to_um(OPTIMIZATION_GAP_CM)
        remaining_um = max(0, teen_engine1_cap_um - prior_engine1_um)
        engine1_delta_um = min(max(0, engine1_delta_um), remaining_um)

    if age >= 21 and state.total_recoverable_loss_um > 0:
        # Section 12.1 carry-over rule:
        # adult remaining deficit must be based on historical posture gain only.
        prior_total_um = 0
        prior_rows = HeightLedger.objects.filter(user=user, entry_type="daily_compute")
        for row in prior_rows:
            try:
                prior_total_um += int((row.metadata or {}).get("engine1_delta_um", 0) or 0)
            except Exception:
                logger.exception(
                    "compute_daily_height_for_user: failed reading engine1_delta_um for adult carry-over",
                    extra={"row_id": getattr(row, "id", None)},
                )
        remaining_um = max(0, int(state.total_recoverable_loss_um) - prior_total_um)
        total_today_um = max(0, engine1_delta_um + engine2_delta_um)
        total_today_um = min(total_today_um, remaining_um)
        # Preserve engine1 priority for adult posture recovery.
        engine1_delta_um = min(engine1_delta_um, total_today_um)
        engine2_delta_um = max(0, total_today_um - engine1_delta_um)
        engine2_delta_dm = int(engine2_delta_um) * 10

    # Final daily delta (teens include biological auto gain).
    delta_um = max(0, int(engine1_delta_um + engine2_delta_um + bio_delta_um))
    delta_cm = round(delta_um / 10000.0, 4)
    if state:
        # Section 4.1 gate (adults): block only when both scan and questionnaire are incomplete.
        if age >= 21 and (not state.scan_completed) and (not state.questionnaire_completed):
            delta_cm = 0.0
            delta_um = 0
            engine1_delta_um = 0
            engine2_delta_um = 0
            engine2_delta_dm = 0
            bio_delta_um = 0
        # Teens require scan before posture/hgh gains, but biological growth still applies.
        if 13 <= age <= 20 and (not state.scan_completed):
            engine1_delta_um = 0
            engine2_delta_um = 0
            engine2_delta_dm = 0
            delta_um = max(0, int(bio_delta_um))
            delta_cm = round(delta_um / 10000.0, 4)

    # Cumulative gain must not lose Engine2 half-micron increments.
    # Re-derive cumulative from atomic per-day columns:
    # total_um = SUM(engine1_delta_um) + SUM(bio_delta_um) + ROUND(SUM(engine2_delta_dm) / 10)
    prior_engine1_um, prior_bio_um, prior_engine2_dm = _sum_prior_engine_deltas(user)
    new_cum = (
        max(0, prior_engine1_um)
        + max(0, prior_bio_um)
        + int(round(max(0, prior_engine2_dm) / 10.0))
        + max(0, int(engine1_delta_um))
        + max(0, int(bio_delta_um))
        + int(round(max(0, int(engine2_delta_dm)) / 10.0))
    )

    HeightLedger.objects.create(
        user=user,
        log_date=log_date,
        entry_type="daily_compute",
        delta_um=max(0, delta_um),
        cumulative_um=new_cum,
        engine1_delta_um=max(0, int(engine1_delta_um)),
        bio_delta_um=max(0, int(bio_delta_um)),
        engine2_delta_dm=max(0, int(engine2_delta_dm)),
        algorithm_version="v1",
        metadata={
            "engine1_points": e1,
            "engine2_points": e2,
            "engine1_delta_um": int(engine1_delta_um),
            # Store both for backward compatibility; dm is authoritative for Engine2 precision.
            "engine2_delta_dm": int(engine2_delta_dm),
            "engine2_delta_um": int(engine2_delta_um),
            "bio_delta_um": int(bio_delta_um),
            "scan_completed": bool(state and state.scan_completed),
        },
    )
    if age >= 21 and state:
        _redistribute_engine1_gain_across_segments(state, engine1_delta_um)
    return {
        "user_id": user.id,
        "delta_um": max(0, delta_um),
        "cumulative_um": new_cum,
    }


def users_for_runtime():
    return User.objects.filter(is_active=True)


def users_for_notifications(now=None):
    now = now or timezone.now()
    today = now.date()
    return users_for_runtime(), today


def get_user_runtime_state_snapshot(user):
    state = _get_or_create_state(user)
    latest_ledger = HeightLedger.objects.filter(user=user).order_by("-created_at").first()
    return {
        "scan_completed": bool(state.scan_completed),
        "questionnaire_completed": bool(state.questionnaire_completed),
        "total_recoverable_loss_um": int(state.total_recoverable_loss_um or 0),
        "spinal_current_loss_um": int(state.spinal_current_loss_um or 0),
        "collapse_current_loss_um": int(state.collapse_current_loss_um or 0),
        "pelvic_current_loss_um": int(state.pelvic_current_loss_um or 0),
        "legs_current_loss_um": int(state.legs_current_loss_um or 0),
        "current_height_um": int(latest_ledger.cumulative_um) if latest_ledger else None,
        "last_scan_at": state.last_scan_at,
    }
