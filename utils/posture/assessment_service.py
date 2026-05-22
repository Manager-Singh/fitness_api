"""Persist posture assessment events and trigger state reconciliation."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.utils import timezone

from posture.models import PostureAssessment
from utils.posture.state_recalculator import (
    apply_scan_total_regression_guard,
    recalculate_posture_state,
)
from utils.posture.state_to_breakdown import (
    breakdown_to_segment_um,
    posture_bars_to_segment_um,
)


def save_questionnaire_assessment(
    user,
    optimization_breakdown: dict,
    *,
    raw_data: dict | None = None,
) -> PostureAssessment:
    """Deactivate prior questionnaire assessment and create a new active row."""
    segment_um = breakdown_to_segment_um(optimization_breakdown)
    PostureAssessment.objects.filter(
        user=user,
        source=PostureAssessment.SOURCE_QUESTIONNAIRE,
        is_active=True,
    ).update(is_active=False)

    assessment = PostureAssessment.objects.create(
        user=user,
        source=PostureAssessment.SOURCE_QUESTIONNAIRE,
        spinal_loss_um=segment_um["spinal"],
        collapse_loss_um=segment_um["collapse"],
        pelvic_loss_um=segment_um["pelvic"],
        legs_loss_um=segment_um["legs"],
        total_loss_um=segment_um["total"],
        confidence_score=Decimal("1.00"),
        is_active=True,
        completed_at=timezone.now(),
        raw_data=raw_data,
    )
    recalculate_posture_state(user)
    from users.models import PostureState

    state, _ = PostureState.objects.get_or_create(user=user)
    state.questionnaire_completed = True
    if state.questionnaire_completed_at is None:
        state.questionnaire_completed_at = timezone.now()
    state.save(
        update_fields=[
            "questionnaire_completed",
            "questionnaire_completed_at",
            "updated_at",
        ]
    )
    return assessment


def save_scan_assessment(
    user,
    posture_bars: dict,
    *,
    source: str = PostureAssessment.SOURCE_SCAN,
    confidence_score: float = 0.85,
    raw_data: dict | None = None,
) -> PostureAssessment:
    """Deactivate prior scan/mock assessment, save row, recalc, then apply total regression guard."""
    if source not in (
        PostureAssessment.SOURCE_SCAN,
        PostureAssessment.SOURCE_MOCK_SCAN,
    ):
        source = PostureAssessment.SOURCE_SCAN

    segment_um = posture_bars_to_segment_um(posture_bars)
    PostureAssessment.objects.filter(
        user=user,
        source=source,
        is_active=True,
    ).update(is_active=False)

    conf = max(0.0, min(1.0, float(confidence_score)))
    assessment = PostureAssessment.objects.create(
        user=user,
        source=source,
        spinal_loss_um=segment_um["spinal"],
        collapse_loss_um=segment_um["collapse"],
        pelvic_loss_um=segment_um["pelvic"],
        legs_loss_um=segment_um["legs"],
        total_loss_um=segment_um["total"],
        confidence_score=Decimal(str(round(conf, 2))),
        is_active=True,
        completed_at=timezone.now(),
        raw_data=raw_data or {"posture_bars": posture_bars},
    )
    recalculate_posture_state(user)
    apply_scan_total_regression_guard(user, segment_um["total"])
    return assessment


def assessment_response_meta(user, assessment: PostureAssessment | None) -> dict[str, Any]:
    """API metadata: assessment id, sources used, routine_regenerated flag."""
    state = getattr(user, "posture_state", None)
    if state is None:
        from users.models import PostureState

        state = PostureState.objects.filter(user=user).first()

    from workouts.models import UserRoutine

    routine = (
        UserRoutine.objects.filter(user=user, is_active=True)
        .order_by("-created_at")
        .first()
    )
    meta = {
        "assessment_id": assessment.id if assessment else None,
        "sources_used": getattr(state, "assessment_sources_used", "") or "",
        "routine_regenerated": bool((routine.scan_score or {}).get("routine_regenerated", False))
        if routine
        else False,
    }
    if routine and routine.posture_snapshot_at_generation:
        meta["new_routine_snapshot"] = routine.posture_snapshot_at_generation
    return meta
