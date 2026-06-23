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
from utils.paywall_flags import effective_is_paid, is_adult_age, is_teen_age, teen_paywall_disabled
from utils.posture.height_constants import (
    OPTIMIZATION_GAP_CM,
    POINTS_TO_CM_ENGINE1,
    POINTS_TO_CM_ENGINE2,
    POSTURE_SEGMENT_DISTRIBUTION_RATIO,
    apportion_by_ratio,
)
from utils.user_time import user_today
from utils.posture.teen_genetic_average import (
    compute_daily_genetic_average_gain_cm,
    compute_genetic_average_cm,
)

import logging

logger = logging.getLogger(__name__)

# v3.3: teen pre-scan pending Engine1 posture gains.
LEDGER_ENTRY_DAILY_COMPUTE = "daily_compute"
LEDGER_ENTRY_PENDING_PRE_SCAN = "pending_pre_scan"
LEDGER_ENTRY_APPLY_PENDING = "apply_pending"


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
    qs = HeightLedger.objects.filter(
        user=user,
        entry_type__in=[LEDGER_ENTRY_DAILY_COMPUTE, LEDGER_ENTRY_APPLY_PENDING],
    )
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
    from workouts.models import RoutineType, Tier as RoutineTier, UserRoutineExercise
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

    is_adult_for_day = is_adult_age(age_years=age, user=user)
    is_teen_for_day = is_teen_age(age_years=age, user=user)

    def _core_done(routine_type):
        completed = set(
            WorkoutEntry.objects.filter(
                session__user=user,
                session__date=log_date,
                session__user_routine__routine_type=routine_type,
                user_routine_exercise__tier=RoutineTier.CORE,
            ).values_list("user_routine_exercise_id", flat=True)
        )
        required = set(
            UserRoutineExercise.objects.filter(
                routine__user=user,
                routine__is_active=True,
                routine__routine_type=routine_type,
                tier=RoutineTier.CORE,
            ).values_list("id", flat=True)
        )
        if not required:
            return False
        return required.issubset(completed)

    if is_adult_for_day:
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
    elif is_teen_for_day:
        core_posture_done = _core_done(RoutineType.POSTURE)
        any_food = NutraEntry.objects.filter(
            session__user=user,
            session__date=log_date,
            food__isnull=False,
        ).exists()
        daily.validated = bool(core_posture_done and any_food)
    else:
        daily.validated = False

    daily.save(update_fields=["validated", "updated_at"])
    return daily


def _posture_unlocked_for_segment_redistribution(state) -> bool:
    """Teen/adult: apply Engine-1 bar updates after scan, questionnaire, or reconciliation assessment."""
    if not state:
        return False
    if bool(state.scan_completed) or bool(state.questionnaire_completed):
        return True
    return bool(str(getattr(state, "assessment_sources_used", "") or "").strip())


SEGMENT_FIELD_RATIO = {
    "spinal_current_loss_um": POSTURE_SEGMENT_DISTRIBUTION_RATIO["spinal_compression"],
    "collapse_current_loss_um": POSTURE_SEGMENT_DISTRIBUTION_RATIO["posture_collapse"],
    "pelvic_current_loss_um": POSTURE_SEGMENT_DISTRIBUTION_RATIO["pelvic_tilt_back"],
    "legs_current_loss_um": POSTURE_SEGMENT_DISTRIBUTION_RATIO["leg_hamstring"],
}

PILLAR_TO_STATE_FIELD = {
    "spinal": "spinal_current_loss_um",
    "collapse": "collapse_current_loss_um",
    "pelvic": "pelvic_current_loss_um",
    "legs": "legs_current_loss_um",
}

STATE_FIELD_TO_PILLAR = {v: k for k, v in PILLAR_TO_STATE_FIELD.items()}


def compute_engine1_gain_shares(state, engine1_gain_um) -> dict[str, int]:
    """
    Section 4.3 / §9 — share of today's Engine-1 gain (μm) applied to each segment's
    Current_Loss.

    Per spec v34: the daily gain is split across ACTIVE segments (Current_Loss > 0)
    by the FIXED segment ratios (30/35/25/10), renormalized over the active set:

        share[s] = Daily_Gain × (segment_ratio[s] / Σ segment_ratio[active])

    Each share is capped at that segment's remaining Current_Loss. Worked example
    from the spec (spinal already at 0): Collapse 35/70=50%, Pelvic 25/70≈36%,
    Legs 10/70≈14%.
    """
    gain_um = max(0, int(engine1_gain_um or 0))
    seg_defs = list(SEGMENT_FIELD_RATIO.keys())
    if gain_um <= 0 or not state:
        return {f: 0 for f in seg_defs}

    active = {}
    for field in seg_defs:
        cur = max(0, int(getattr(state, field, 0) or 0))
        if cur > 0:
            active[field] = cur
    if not active:
        return {f: 0 for f in seg_defs}

    weights = {field: SEGMENT_FIELD_RATIO[field] for field in active}
    apportioned = apportion_by_ratio(weights, gain_um, active)

    shares = {f: 0 for f in seg_defs}
    shares.update(apportioned)
    return shares


def _redistribute_engine1_gain_across_segments(state, engine1_gain_um):
    """
    Section 4.3 — apply today's Engine-1 height gain (μm) to segment Current_Loss.

    Daily gain is split across active segments by the fixed segment ratios
    (30/35/25/10) renormalized over the active set (see compute_engine1_gain_shares).
    """
    gain_um = max(0, int(engine1_gain_um or 0))
    if gain_um <= 0:
        return {}

    shares = compute_engine1_gain_shares(state, gain_um)
    for field, share in shares.items():
        if share <= 0:
            continue
        cur = max(0, int(getattr(state, field, 0) or 0))
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
    return shares


def _cap_segment_shares_to_state(state, shares_by_pillar: dict[str, int]) -> dict[str, int]:
    capped = {p: 0 for p in PILLAR_TO_STATE_FIELD}
    if not state:
        return capped
    for pillar, field in PILLAR_TO_STATE_FIELD.items():
        raw = max(0, int(shares_by_pillar.get(pillar, 0) or 0))
        remaining = max(0, int(getattr(state, field, 0) or 0))
        capped[pillar] = min(raw, remaining)
    return capped


def _limit_segment_shares_to_total(shares_by_pillar: dict[str, int], max_total_um: int) -> dict[str, int]:
    max_total_um = max(0, int(max_total_um or 0))
    shares = {p: max(0, int(shares_by_pillar.get(p, 0) or 0)) for p in PILLAR_TO_STATE_FIELD}
    total = sum(shares.values())
    if max_total_um <= 0:
        return {p: 0 for p in shares}
    if total <= max_total_um:
        return shares
    apportioned = apportion_by_ratio(
        {p: amount for p, amount in shares.items() if amount > 0},
        max_total_um,
        shares,
    )
    return {p: int(apportioned.get(p, 0) or 0) for p in shares}


def compute_targeted_engine1_recovery(user, log_date, age, state, adult_nutrition_points, habit_points) -> dict:
    """
    Monday work order targeted Engine-1 crediting:
    posture exercise points credit primary/secondary 70/30; nutrition/habit shares
    are collected only by pillars primary-trained by at least one completed posture exercise.
    """
    from workouts.exercise_assignment_data import primary_secondary_for_exercise
    from workouts.models import ExerciseCategory

    shares = {p: 0 for p in PILLAR_TO_STATE_FIELD}
    exercise_shares = {p: 0 for p in PILLAR_TO_STATE_FIELD}
    bonus_shares = {p: 0 for p in PILLAR_TO_STATE_FIELD}
    trained_today: set[str] = set()
    workouts_done = False

    workout_qs = WorkoutEntry.objects.filter(session__user=user, session__date=log_date).select_related(
        "exercise",
        "session__user_routine",
    )
    for entry in workout_qs:
        workouts_done = True
        ex = getattr(entry, "exercise", None)
        if not ex:
            continue
        routine = getattr(getattr(entry, "session", None), "user_routine", None)
        routine_type = str(getattr(routine, "routine_type", "") or "").lower()
        category = str(getattr(ex, "category", "") or "").lower()
        if routine_type == "hgh" or category == ExerciseCategory.HGH or getattr(ex, "teen_only", False):
            continue
        primary, secondary = primary_secondary_for_exercise(ex)
        if not primary:
            continue
        trained_today.add(primary)
        secondary = secondary or primary
        pts = max(0.0, float(getattr(entry, "points", 0) or 0))
        recovery_um = int(round(pts * 10.0))
        primary_um = int(round(recovery_um * 0.70))
        secondary_um = max(0, recovery_um - primary_um)
        exercise_shares[primary] += primary_um
        exercise_shares[secondary] += secondary_um

    for pillar, amount in exercise_shares.items():
        shares[pillar] += amount

    if workouts_done:
        is_adult = is_adult_age(age_years=age, user=user)
        eligible_pts = float(adult_nutrition_points or 0) + float(habit_points or 0) if is_adult else float(habit_points or 0)
        share_um = int(round(max(0.0, eligible_pts) * 10.0 / 4.0))
        for pillar in trained_today:
            bonus_shares[pillar] += share_um
            shares[pillar] += share_um

    capped = _cap_segment_shares_to_state(state, shares)
    return {
        "engine1_segment_shares_um": capped,
        "engine1_segment_raw_shares_um": shares,
        "exercise_segment_shares_um": exercise_shares,
        "strict_share_segment_shares_um": bonus_shares,
        "trained_primary_pillars": sorted(trained_today),
        "workouts_done_today": bool(workouts_done),
        "forfeited_share_pillars": [
            p for p in PILLAR_TO_STATE_FIELD if workouts_done and p not in trained_today
        ],
        "engine1_delta_um": sum(capped.values()),
    }


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
        if not is_adult_age(age_years=row_age, user=user):
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
    from habits.models import MicroHabitLog

    habit_days = list(
        MicroHabitLog.objects.filter(user=user, log_date__gte=from_date)
        .values_list("log_date", flat=True)
        .distinct()
    )
    days = sorted({from_date, *dailylog_days, *workout_days, *nutra_days, *habit_days})
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


def _daily_raw_source_points(user, log_date):
    """
    Bug 14 — single source of truth for the day's RAW (pre-cap, pre-engine-routing) points
    per source. Used by both the engine-point compute and the audit breakdown so the two
    can never drift. Returns a dict of floats:
        posture, hgh, food, sleep, sun, meditation, hydration
    Monday work order: HGH routes to Engine 2 and has no per-category cap.
    """
    workout_qs = WorkoutEntry.objects.filter(session__user=user, session__date=log_date).select_related(
        "session__user_routine"
    )
    posture_pts = 0.0
    hgh_pts = 0.0
    from workouts.models import ExerciseCategory

    for w in workout_qs:
        session = getattr(w, "session", None)
        user_routine = getattr(session, "user_routine", None)
        rt = str(getattr(user_routine, "routine_type", "") or "").lower()
        ex = getattr(w, "exercise", None)
        category = str(getattr(ex, "category", "") or "").lower()
        pts = float(w.points or 0)
        if rt == "hgh" or category == ExerciseCategory.HGH or bool(getattr(ex, "teen_only", False)):
            hgh_pts += pts
        else:
            posture_pts += pts

    nutra_qs = NutraEntry.objects.filter(session__user=user, session__date=log_date).select_related("module")
    food_pts = 0.0
    sleep_pts = 0.0
    sun_pts = 0.0
    med_pts = 0.0
    hyd_pts = 0.0
    for n in nutra_qs:
        pts = float(n.score or 0)
        module = getattr(n, "module", None)
        module_name = str(getattr(module, "name", "") or "").lower()
        if n.food_id:
            food_pts += pts
            continue
        if "sleep" in module_name:
            sleep_pts += pts
        elif "sun" in module_name:
            sun_pts += pts
        elif "meditat" in module_name:
            med_pts += pts
        elif ("hydrat" in module_name) or ("water" in module_name):
            hyd_pts += pts

    return {
        "posture": posture_pts,
        "hgh": hgh_pts,
        "food": food_pts,
        "sleep": sleep_pts,
        "sun": sun_pts,
        "meditation": med_pts,
        "hydration": hyd_pts,
    }


def _daily_engine_points(user, log_date, age, subscription_data):
    """
    Section 11 routing/caps on current day data.
    Returns (engine1_points, engine2_points, exercise_points, food_points, lifestyle_points, habit_points)
    """
    from habits.services import capped_habit_points_for_engine

    habit_pts = float(capped_habit_points_for_engine(user, log_date))
    raw = _daily_raw_source_points(user, log_date)
    posture_pts = raw["posture"]
    hgh_pts = raw["hgh"]
    food_pts = raw["food"]
    sleep_pts = raw["sleep"]
    sun_pts = raw["sun"]
    med_pts = raw["meditation"]
    hyd_pts = raw["hydration"]

    exercise_points = int(round(posture_pts + hgh_pts))
    lifestyle_points = int(round(sleep_pts + sun_pts + med_pts + hyd_pts))
    food_points = int(round(food_pts))

    # Sex-specific adult band (female 18+, male 21+) so nutrition routing matches
    # /api/my-nutrition-plan, /api/dashboard-new and /api/adult-nutrition.
    if is_adult_age(age_years=age, user=user):
        # Part 2 — adult Engine 1 nutrition = protein + hydration points (cap 15),
        # server-authoritative from AdultNutritionDay. Gated by posture work exactly as
        # adult nutrition routes today.
        from utils.adult_nutrition import adult_nutrition_points_today

        nutrition_for_engine = (
            int(adult_nutrition_points_today(user, log_date)) if posture_pts > 0 else 0
        )
        return (
            posture_pts + nutrition_for_engine + habit_pts,
            0.0,
            exercise_points,
            # Display "nutrition" bucket reflects the adult protein+hydration points.
            int(nutrition_for_engine),
            0,  # adults have no Lifestyle tab — water/sleep live in AdultNutritionDay
            int(habit_pts),
        )

    trial_day = subscription_data.get("trial_day")
    is_paid = effective_is_paid(user, subscription_data)
    is_trial = bool(subscription_data.get("is_trial", False))
    trial_expired_unpaid = bool((not is_paid) and (not is_trial) and trial_day is not None and int(trial_day) > 7)
    if teen_paywall_disabled():
        trial_expired_unpaid = False

    if trial_expired_unpaid:
        return 0.0, 0.0, exercise_points, food_points, lifestyle_points, 0

    engine1 = posture_pts + habit_pts
    if exercise_points <= 0:
        # Zero-log day: lifestyle still eligible for engine2.
        engine2 = min(sleep_pts, 10.0) + min(sun_pts, 6.0) + min(med_pts, 2.0) + min(hyd_pts, 1.0)
        return engine1, engine2, exercise_points, food_points, lifestyle_points, int(habit_pts)

    engine2 = (
        hgh_pts
        + min(food_pts, 35.0)
        + min(sleep_pts, 10.0)
        + min(sun_pts, 6.0)
        + min(med_pts, 2.0)
        + min(hyd_pts, 1.0)
    )
    return engine1, engine2, exercise_points, food_points, lifestyle_points, int(habit_pts)


def daily_points_source_breakdown(user, log_date, age, subscription_data) -> dict:
    """
    Bug 14 — full per-source accounting for a day's points so a reported total (e.g. the
    "137 points / 0.091 cm" case) can be reconciled: which source produced each point,
    which engine it routes to, which caps applied, and the resulting cm before the
    lifetime / deficit / pre-assessment gates in compute_daily_height_for_user().

    The engine1_points / engine2_points here are taken straight from _daily_engine_points,
    so this audit can never disagree with the values actually written to the ledger.
    """
    from habits.services import (
        DAILY_HABIT_CAP,
        capped_habit_points_for_engine,
        total_raw_habit_points,
    )

    raw = _daily_raw_source_points(user, log_date)
    habits_raw = int(total_raw_habit_points(user, log_date))
    habits_capped = int(capped_habit_points_for_engine(user, log_date))
    e1, e2, exercise_points, food_points, lifestyle_points, habit_points = _daily_engine_points(
        user=user, log_date=log_date, age=age, subscription_data=subscription_data
    )
    is_adult = is_adult_age(age_years=age, user=user)

    adult_nutrition_engine_pts = 0
    if is_adult:
        # Part 2 — adult nutrition (protein+hydration) gated by posture work.
        from utils.adult_nutrition import adult_nutrition_points_today

        adult_nutrition_engine_pts = (
            int(adult_nutrition_points_today(user, log_date)) if raw["posture"] > 0 else 0
        )

    # Traceable daily-points total (the user-facing "points today", like the dashboard):
    # everything logged, before engine caps. For adults the food/lifestyle NutraEntry
    # buckets are retired, so their nutrition is the protein+hydration points instead.
    adult_nutrition_logged = 0
    if is_adult:
        from utils.adult_nutrition import adult_nutrition_points_today

        adult_nutrition_logged = int(adult_nutrition_points_today(user, log_date))
    daily_points_total = int(round(
        raw["posture"] + raw["hgh"] + raw["food"]
        + raw["sleep"] + raw["sun"] + raw["meditation"] + raw["hydration"]
        + habits_raw + adult_nutrition_logged
    ))

    engine1_cm = round(float(e1) * POINTS_TO_CM_ENGINE1, 6)
    engine2_cm = round(float(e2) * POINTS_TO_CM_ENGINE2, 6)

    return {
        "log_date": str(log_date),
        "age": int(age),
        "tier": "adult" if is_adult else "teen",
        "raw_sources": {k: round(float(v), 3) for k, v in raw.items()},
        "habits": {"raw": habits_raw, "capped": habits_capped, "cap": int(DAILY_HABIT_CAP)},
        "engine1": {
            "points": int(round(float(e1))),
            "cm_per_point": POINTS_TO_CM_ENGINE1,
            "cm": engine1_cm,
            "contributors": (
                ["posture", "adult_nutrition_flat", "habits"] if is_adult else ["posture", "habits"]
            ),
            "adult_nutrition_engine_points": adult_nutrition_engine_pts if is_adult else None,
        },
        "engine2": {
            "points": int(round(float(e2))),
            "cm_per_point": POINTS_TO_CM_ENGINE2,
            "cm": engine2_cm,
            "caps": (
                {} if is_adult else {"hgh": None, "food": 35, "sleep": 10, "sun": 6, "meditation": 2, "hydration": 1}
            ),
        },
        "daily_points_total": daily_points_total,
        "engine_cm_uncapped_total": round(engine1_cm + engine2_cm, 6),
        "notes": [
            "engine_cm_uncapped_total is BEFORE the teen 5.5cm lifetime cap, the adult "
            "remaining-deficit carry-over cap, and the pre-assessment gates; the ledger "
            "row's engine1_delta_um/engine2_delta_dm reflect those.",
            "Adult lifestyle (sleep/sun/meditation/hydration) and raw food are diary-only "
            "(not Engine-1); adult nutrition uses a flat 1 pt per unique disc/muscle food.",
        ],
    }


def _safe_daily_points_breakdown(user, log_date, age, subscription_data) -> dict:
    """Never let the audit breakdown break the daily compute / ledger write."""
    try:
        return daily_points_source_breakdown(user, log_date, age, subscription_data)
    except Exception:
        logger.exception(
            "daily_points_source_breakdown failed",
            extra={"user_id": getattr(user, "id", None), "log_date": str(log_date)},
        )
        return {}


def compute_daily_height_for_user(user, log_date=None, force_recompute=False):
    log_date = log_date or user_today(user)
    state = _get_or_create_state(user)
    existing = HeightLedger.objects.filter(
        user=user,
        log_date=log_date,
        entry_type=LEDGER_ENTRY_DAILY_COMPUTE,
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
            entry_type=LEDGER_ENTRY_DAILY_COMPUTE,
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
    e1, e2, exercise_points, food_points, lifestyle_points, habit_points = _daily_engine_points(
        user=user,
        log_date=log_date,
        age=age,
        subscription_data=subscription_data,
    )

    daily, _ = DailyLog.objects.get_or_create(user=user, log_date=log_date)
    daily.exercise_points = exercise_points
    daily.food_points = food_points
    daily.lifestyle_points = lifestyle_points
    daily.habit_points = habit_points
    daily.engine1_points = int(round(float(e1)))
    daily.engine2_points = int(round(float(e2)))
    if is_teen_for_day:
        try:
            daily.genetic_average_cm = float(compute_genetic_average_cm(user, log_date))
            daily.daily_genetic_average_gain_cm = float(
                compute_daily_genetic_average_gain_cm(user, log_date)
            )
        except Exception:
            logger.exception(
                "compute_daily_height_for_user: genetic average fields failed",
                extra={"user_id": getattr(user, "id", None), "log_date": str(log_date)},
            )
            daily.genetic_average_cm = None
            daily.daily_genetic_average_gain_cm = None
    else:
        daily.genetic_average_cm = None
        daily.daily_genetic_average_gain_cm = None
    daily.save()
    # Strict spec validation for streak/leaderboard correctness.
    set_daily_validated(user, log_date)

    # Section 11 formulas and routing. Displayed Engine-1 points remain full; actual
    # posture recovery is targeted to trained pillars by the Monday work order.
    targeted_engine1 = compute_targeted_engine1_recovery(
        user=user,
        log_date=log_date,
        age=age,
        state=state,
        adult_nutrition_points=food_points if is_adult_for_day else 0,
        habit_points=habit_points,
    )
    engine1_segment_shares_um = dict(targeted_engine1.get("engine1_segment_shares_um") or {})
    engine1_delta_um = int(targeted_engine1.get("engine1_delta_um") or 0)
    # Engine2 must preserve 0.5 μm increments: store as dμm, derive μm only for legacy totals.
    engine2_delta_dm = _to_dm_from_engine2_points(e2)
    engine2_delta_um = _um_from_dm(engine2_delta_dm)
    bio_delta_um = 0

    if is_teen_for_day:
        profile = UserProfile.objects.filter(user=user).first()
        base_height_cm = float(getattr(profile, "base_height_cm", None) or getattr(profile, "current_height_cm", 0) or 0)
        bio_delta_um = _to_um(_interpolated_teen_bio_gain_cm(user, base_height_cm, on_date=log_date))
        prior_engine1_um = 0
        prior_rows = HeightLedger.objects.filter(
            user=user,
            entry_type__in=[LEDGER_ENTRY_DAILY_COMPUTE, LEDGER_ENTRY_APPLY_PENDING],
        )
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
        engine1_segment_shares_um = _limit_segment_shares_to_total(engine1_segment_shares_um, remaining_um)
        engine1_delta_um = sum(engine1_segment_shares_um.values())
        targeted_engine1["engine1_segment_shares_um"] = engine1_segment_shares_um
        targeted_engine1["engine1_delta_um"] = engine1_delta_um

    if is_adult_for_day and state.total_recoverable_loss_um > 0:
        # Section 12.1 carry-over rule:
        # adult remaining deficit must be based on historical posture gain only.
        prior_total_um = 0
        prior_rows = HeightLedger.objects.filter(
            user=user,
            entry_type__in=[LEDGER_ENTRY_DAILY_COMPUTE, LEDGER_ENTRY_APPLY_PENDING],
        )
        for row in prior_rows:
            try:
                prior_total_um += int((row.metadata or {}).get("engine1_delta_um", 0) or 0)
            except Exception:
                logger.exception(
                    "compute_daily_height_for_user: failed reading engine1_delta_um for adult carry-over",
                    extra={"row_id": getattr(row, "id", None)},
                )
        remaining_um = max(0, int(state.total_recoverable_loss_um) - prior_total_um)
        engine1_segment_shares_um = _limit_segment_shares_to_total(engine1_segment_shares_um, remaining_um)
        engine1_delta_um = sum(engine1_segment_shares_um.values())
        targeted_engine1["engine1_segment_shares_um"] = engine1_segment_shares_um
        targeted_engine1["engine1_delta_um"] = engine1_delta_um
        engine2_delta_um = 0
        engine2_delta_dm = int(engine2_delta_um) * 10

    # Final daily delta (teens include biological auto gain).
    delta_um = max(0, int(engine1_delta_um + engine2_delta_um + bio_delta_um))
    delta_cm = round(delta_um / 10000.0, 4)
    if state:
        # Section 4.1 gate (adults): block only when both scan and questionnaire are incomplete.
        if is_adult_for_day and (not state.scan_completed) and (not state.questionnaire_completed):
            delta_cm = 0.0
            delta_um = 0
            engine1_delta_um = 0
            engine1_segment_shares_um = {p: 0 for p in PILLAR_TO_STATE_FIELD}
            targeted_engine1["engine1_segment_shares_um"] = engine1_segment_shares_um
            targeted_engine1["engine1_delta_um"] = 0
            engine2_delta_um = 0
            engine2_delta_dm = 0
            bio_delta_um = 0
        # v3.3 teen pre-scan rules:
        # - If BOTH scan and questionnaire are incomplete: bio applies, engine2 blocked,
        #   engine1 is stored as pending and does not affect displayed height until unlock.
        # - If questionnaire is complete (even without scan): allow engine1/engine2 normally.
        if is_teen_for_day and (not state.scan_completed) and (not state.questionnaire_completed):
            pending_engine1_um = max(0, int(engine1_delta_um))
            engine1_delta_um = 0
            engine1_segment_shares_um = {p: 0 for p in PILLAR_TO_STATE_FIELD}
            targeted_engine1["engine1_segment_shares_um"] = engine1_segment_shares_um
            targeted_engine1["engine1_delta_um"] = 0
            engine2_delta_um = 0
            engine2_delta_dm = 0
            delta_um = max(0, int(bio_delta_um))
            delta_cm = round(delta_um / 10000.0, 4)
        else:
            pending_engine1_um = 0

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
        entry_type=LEDGER_ENTRY_DAILY_COMPUTE,
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
            "engine1_segment_shares_um": engine1_segment_shares_um,
            "targeted_engine1": targeted_engine1,
            # Bug 14 — per-source audit so any day's points total can be reconciled.
            "daily_points_breakdown": _safe_daily_points_breakdown(user, log_date, age, subscription_data),
        },
    )
    if is_teen_for_day and pending_engine1_um > 0:
        # Store pending posture gain for v3.3 teen pre-scan state.
        HeightLedger.objects.create(
            user=user,
            log_date=log_date,
            entry_type=LEDGER_ENTRY_PENDING_PRE_SCAN,
            delta_um=0,
            cumulative_um=new_cum,
            engine1_delta_um=int(pending_engine1_um),
            bio_delta_um=0,
            engine2_delta_dm=0,
            algorithm_version="v1",
            metadata={
                "engine1_points": e1,
                "engine1_delta_um": int(pending_engine1_um),
                "pending": True,
                "reason": "teen_pre_scan",
            },
        )

    # Section 4.3: derive segment Current_Loss deterministically from the assessment
    # baseline minus cumulative Engine-1 recovery (now that today's ledger row exists).
    # This is idempotent, so force_recompute / rebuild can't compound the reduction and
    # drive the optimization bars past the real recovery.
    if state and (is_adult_for_day or _posture_unlocked_for_segment_redistribution(state)):
        try:
            from utils.posture.state_recalculator import resync_segment_losses_from_baseline

            resync_segment_losses_from_baseline(user)
        except Exception:
            logger.exception(
                "compute_daily_height_for_user: segment resync failed",
                extra={"user_id": getattr(user, "id", None), "log_date": str(log_date)},
            )
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
    latest_ledger = HeightLedger.objects.filter(
        user=user,
        entry_type__in=[LEDGER_ENTRY_DAILY_COMPUTE, LEDGER_ENTRY_APPLY_PENDING],
    ).order_by("-created_at").first()
    return {
        "scan_completed": bool(state.scan_completed),
        "questionnaire_completed": bool(state.questionnaire_completed),
        "assessment_sources_used": getattr(state, "assessment_sources_used", "") or "",
        "total_recoverable_loss_um": int(state.total_recoverable_loss_um or 0),
        "spinal_current_loss_um": int(state.spinal_current_loss_um or 0),
        "collapse_current_loss_um": int(state.collapse_current_loss_um or 0),
        "pelvic_current_loss_um": int(state.pelvic_current_loss_um or 0),
        "legs_current_loss_um": int(state.legs_current_loss_um or 0),
        "current_height_um": int(latest_ledger.cumulative_um) if latest_ledger else None,
        "last_scan_at": state.last_scan_at,
    }


def apply_pending_pre_scan_engine1(user, when=None):
    """
    v3.3: Apply all teen pre-scan pending Engine1 gains immediately after unlock
    (scan_completed=true OR questionnaire_completed=true).
    """
    when = when or user_today(user)
    pending_rows = list(
        HeightLedger.objects.filter(user=user, entry_type=LEDGER_ENTRY_PENDING_PRE_SCAN)
        .order_by("log_date", "created_at")
        .only("id", "engine1_delta_um", "metadata")
    )
    if not pending_rows:
        return {"applied_um": 0, "rows": 0}

    total_pending_um = 0
    pending_ids = []
    for r in pending_rows:
        try:
            total_pending_um += int(getattr(r, "engine1_delta_um", 0) or 0)
        except Exception:
            continue
        pending_ids.append(r.id)
    total_pending_um = max(0, int(total_pending_um))
    if total_pending_um <= 0 or not pending_ids:
        return {"applied_um": 0, "rows": len(pending_rows)}

    # Derive current cumulative from applied rows only, then add pending.
    prior_engine1_um, prior_bio_um, prior_engine2_dm = _sum_prior_engine_deltas(user)
    prior_total_um = (
        max(0, int(prior_engine1_um))
        + max(0, int(prior_bio_um))
        + int(round(max(0, int(prior_engine2_dm)) / 10.0))
    )
    new_cum = prior_total_um + total_pending_um

    HeightLedger.objects.create(
        user=user,
        log_date=when,
        entry_type=LEDGER_ENTRY_APPLY_PENDING,
        delta_um=int(total_pending_um),
        cumulative_um=int(new_cum),
        engine1_delta_um=int(total_pending_um),
        bio_delta_um=0,
        engine2_delta_dm=0,
        algorithm_version="v1",
        metadata={
            "pending_applied": True,
            "pending_source_entry_type": LEDGER_ENTRY_PENDING_PRE_SCAN,
            "pending_row_ids": pending_ids[:2000],
        },
    )
    # Mark pending rows as applied to avoid re-apply (keep rows for audit).
    HeightLedger.objects.filter(id__in=pending_ids).update(entry_type="pending_pre_scan_applied")

    state, _ = PostureState.objects.get_or_create(user=user)
    if _posture_unlocked_for_segment_redistribution(state):
        try:
            from utils.posture.state_recalculator import resync_segment_losses_from_baseline

            resync_segment_losses_from_baseline(user)
        except Exception:
            logger.exception(
                "apply_pending_pre_scan_engine1: segment resync failed",
                extra={"user_id": getattr(user, "id", None)},
            )

    return {"applied_um": total_pending_um, "rows": len(pending_ids)}
