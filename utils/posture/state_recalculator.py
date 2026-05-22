"""Reconcile questionnaire + scan assessments into derived PostureState."""
from __future__ import annotations

from django.utils import timezone

from posture.models import PostureAssessment
from users.models import HeightLedger, PostureState

SEGMENTS = ("spinal", "collapse", "pelvic", "legs")
PRIMARY_WEIGHT = 0.70
SECONDARY_WEIGHT = 0.30

_SEGMENT_UM_ATTR = {
    "spinal": ("spinal_loss_um", "spinal_current_loss_um"),
    "collapse": ("collapse_loss_um", "collapse_current_loss_um"),
    "pelvic": ("pelvic_loss_um", "pelvic_current_loss_um"),
    "legs": ("legs_loss_um", "legs_current_loss_um"),
}


def recalculate_posture_state(user) -> PostureState:
    """
    Recalculate PostureState from active PostureAssessment rows.
    Newest assessment (by completed_at) is primary at 70%; older source at 30%.
    """
    state, _ = PostureState.objects.get_or_create(user=user)
    previous_snapshot = _snapshot_from_state(state)

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
        return state

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

    state.total_recoverable_loss_um = (
        int(state.spinal_current_loss_um or 0)
        + int(state.collapse_current_loss_um or 0)
        + int(state.pelvic_current_loss_um or 0)
        + int(state.legs_current_loss_um or 0)
    )
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
