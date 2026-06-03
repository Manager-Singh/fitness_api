"""Reconcile questionnaire + scan assessments into derived PostureState."""
from __future__ import annotations

from django.db.models import Sum
from django.utils import timezone

from posture.models import PostureAssessment
from users.models import HeightLedger, PostureState
from utils.posture.height_constants import POSTURE_SEGMENT_DISTRIBUTION_RATIO

SEGMENTS = ("spinal", "collapse", "pelvic", "legs")
PRIMARY_WEIGHT = 0.70
SECONDARY_WEIGHT = 0.30

_SEGMENT_UM_ATTR = {
    "spinal": ("spinal_loss_um", "spinal_current_loss_um"),
    "collapse": ("collapse_loss_um", "collapse_current_loss_um"),
    "pelvic": ("pelvic_loss_um", "pelvic_current_loss_um"),
    "legs": ("legs_loss_um", "legs_current_loss_um"),
}

# §4.3 fixed redistribution ratios keyed by PostureState current-loss field.
_STATE_ATTR_RATIO = {
    "spinal_current_loss_um": POSTURE_SEGMENT_DISTRIBUTION_RATIO["spinal_compression"],
    "collapse_current_loss_um": POSTURE_SEGMENT_DISTRIBUTION_RATIO["posture_collapse"],
    "pelvic_current_loss_um": POSTURE_SEGMENT_DISTRIBUTION_RATIO["pelvic_tilt_back"],
    "legs_current_loss_um": POSTURE_SEGMENT_DISTRIBUTION_RATIO["leg_hamstring"],
}


def _cumulative_engine1_recovery_um(user) -> int:
    """Total Engine-1 (posture) height recovery applied to date, in μm."""
    total = (
        HeightLedger.objects.filter(
            user=user, entry_type__in=("daily_compute", "apply_pending")
        )
        .aggregate(total=Sum("engine1_delta_um"))
        .get("total")
    )
    return max(0, int(total or 0))


def _distribute_recovery_over_baseline(baseline_um: dict, recovered_um: int) -> dict:
    """
    Split cumulative Engine-1 recovery across segments by the fixed §4.3 ratios
    (30/35/25/10) renormalized over segments that still hold baseline loss, capped
    at each segment's baseline. Mirrors compute_engine1_gain_shares semantics so the
    bars reflect real recovery instead of resetting on every reconciliation.
    """
    active = {attr: base for attr, base in baseline_um.items() if base > 0}
    if recovered_um <= 0 or not active:
        return {}
    total_ratio = sum(_STATE_ATTR_RATIO[attr] for attr in active)
    if total_ratio <= 0:
        return {}
    shares = {}
    for attr, base in active.items():
        raw = int(round(recovered_um * (_STATE_ATTR_RATIO[attr] / total_ratio)))
        shares[attr] = min(raw, base)
    return shares


def _derive_assessment_baseline_um(user, state) -> dict | None:
    """
    Set ``state`` segment fields + ``assessment_sources_used`` from active assessments
    (newest source primary at 70%, older at 30%). Returns the per-segment BASELINE
    deficit keyed by PostureState attr, or None when the user has no assessments.
    """
    latest_questionnaire = PostureAssessment.objects.filter(
        user=user,
        source=PostureAssessment.SOURCE_QUESTIONNAIRE,
        is_active=True,
    ).order_by("-completed_at").first()

    latest_scan = (
        PostureAssessment.objects.filter(
            user=user,
            source__in=(PostureAssessment.SOURCE_SCAN, PostureAssessment.SOURCE_MOCK_SCAN),
            is_active=True,
        )
        .order_by("-completed_at")
        .first()
    )

    if not latest_questionnaire and not latest_scan:
        return None

    if latest_questionnaire and not latest_scan:
        _apply_single_assessment(state, latest_questionnaire)
        state.assessment_sources_used = PostureState.ASSESSMENT_SOURCES_QUESTIONNAIRE_ONLY
    elif latest_scan and not latest_questionnaire:
        _apply_single_assessment(state, latest_scan)
        state.assessment_sources_used = PostureState.ASSESSMENT_SOURCES_SCAN_ONLY
    else:
        if latest_scan.completed_at > latest_questionnaire.completed_at:
            primary, secondary = latest_scan, latest_questionnaire
            state.assessment_sources_used = PostureState.ASSESSMENT_SOURCES_BOTH_SCAN_PRIMARY
        else:
            primary, secondary = latest_questionnaire, latest_scan
            state.assessment_sources_used = PostureState.ASSESSMENT_SOURCES_BOTH_QUESTIONNAIRE_PRIMARY
        _apply_blended_assessments(state, primary, secondary)

    return {
        attr: int(getattr(state, attr) or 0)
        for (_loss_attr, attr) in _SEGMENT_UM_ATTR.values()
    }


def _apply_baseline_minus_recovery(user, state, baseline_um: dict, *, set_total: bool) -> None:
    """
    v34 §4.3: Current_Loss = baseline − cumulative Engine-1 recovery (fixed-ratio split).
    This is deterministic — it depends only on the assessment baseline and the ledger,
    so it is idempotent no matter how many times it runs.
    """
    if set_total:
        state.total_recoverable_loss_um = sum(baseline_um.values())
    recovered_um = _cumulative_engine1_recovery_um(user)
    recovery_shares = (
        _distribute_recovery_over_baseline(baseline_um, recovered_um) if recovered_um > 0 else {}
    )
    for attr, base in baseline_um.items():
        setattr(state, attr, max(0, base - recovery_shares.get(attr, 0)))


def recalculate_posture_state(user) -> PostureState:
    """
    Recalculate PostureState from active PostureAssessment rows.
    Newest assessment (by completed_at) is primary at 70%; older source at 30%.
    Recovery already earned (cumulative Engine-1) is preserved, never reset.
    """
    state, _ = PostureState.objects.get_or_create(user=user)
    previous_snapshot = _snapshot_from_state(state)

    baseline_um = _derive_assessment_baseline_um(user, state)
    if baseline_um is None:
        return state

    _apply_baseline_minus_recovery(user, state, baseline_um, set_total=True)

    state.last_recalculated_at = timezone.now()
    state.save(
        update_fields=[
            "spinal_current_loss_um",
            "collapse_current_loss_um",
            "pelvic_current_loss_um",
            "legs_current_loss_um",
            "total_recoverable_loss_um",
            "assessment_sources_used",
            "last_recalculated_at",
            "updated_at",
        ]
    )

    from utils.routine_regeneration_check import check_and_maybe_regenerate_routine

    check_and_maybe_regenerate_routine(user, previous_snapshot)
    return state


def resync_segment_losses_from_baseline(user) -> PostureState:
    """
    Idempotent segment-loss derivation used by the daily height compute.

    Sets Current_Loss = assessment baseline − cumulative Engine-1 recovery, so repeated
    daily computes / force_recompute / rebuilds can never compound the reduction and
    drive the optimization bars past the real, ledger-tracked recovery. Does NOT touch
    total_recoverable_loss_um (managed by reconciliation + the scan regression guard)
    and does NOT trigger routine regeneration.
    """
    state, _ = PostureState.objects.get_or_create(user=user)
    baseline_um = _derive_assessment_baseline_um(user, state)
    if baseline_um is None:
        return state
    _apply_baseline_minus_recovery(user, state, baseline_um, set_total=False)
    state.save(
        update_fields=[
            "spinal_current_loss_um",
            "collapse_current_loss_um",
            "pelvic_current_loss_um",
            "legs_current_loss_um",
            "assessment_sources_used",
            "updated_at",
        ]
    )
    return state


def apply_scan_total_regression_guard(user, new_deficit_um: int) -> PostureState:
    """
    Section 4.3 — preserve scan total_recoverable ceiling / regression guard on total only.
    Called after segment blend when a scan assessment is saved.
    """
    state, _ = PostureState.objects.get_or_create(user=user)
    prev_scan_completed = bool(state.scan_completed)

    historical_posture_um = 0
    for row in HeightLedger.objects.filter(user=user, entry_type="daily_compute"):
        try:
            historical_posture_um += int((row.metadata or {}).get("engine1_delta_um", 0))
        except Exception:
            continue

    if not prev_scan_completed or int(state.total_recoverable_loss_um or 0) <= 0:
        state.total_recoverable_loss_um = new_deficit_um
    else:
        remaining_ceiling_um = int(state.total_recoverable_loss_um or 0) - historical_posture_um
        if new_deficit_um > max(0, remaining_ceiling_um):
            state.total_recoverable_loss_um = historical_posture_um + new_deficit_um

    state.save(update_fields=["total_recoverable_loss_um", "updated_at"])
    return state


def _apply_single_assessment(state: PostureState, assessment: PostureAssessment) -> None:
    for seg in SEGMENTS:
        loss_attr, state_attr = _SEGMENT_UM_ATTR[seg]
        setattr(state, state_attr, int(getattr(assessment, loss_attr, 0) or 0))


def _apply_blended_assessments(
    state: PostureState,
    primary: PostureAssessment,
    secondary: PostureAssessment,
) -> None:
    for seg in SEGMENTS:
        loss_attr, state_attr = _SEGMENT_UM_ATTR[seg]
        primary_loss = int(getattr(primary, loss_attr, 0) or 0)
        secondary_loss = int(getattr(secondary, loss_attr, 0) or 0)
        blended = int((primary_loss * PRIMARY_WEIGHT) + (secondary_loss * SECONDARY_WEIGHT))
        setattr(state, state_attr, blended)


def _snapshot_from_state(state: PostureState) -> dict:
    return {
        "spinal_loss_um": int(state.spinal_current_loss_um or 0),
        "collapse_loss_um": int(state.collapse_current_loss_um or 0),
        "pelvic_loss_um": int(state.pelvic_current_loss_um or 0),
        "legs_loss_um": int(state.legs_current_loss_um or 0),
    }
