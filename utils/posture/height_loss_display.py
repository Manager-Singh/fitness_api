"""Monday B3 — headline Height Loss derived from baseline minus cumulative Engine-1."""
from __future__ import annotations

from users.models import PostureState
from users.spec_runtime import get_user_runtime_state_snapshot
from utils.posture.state_recalculator import (
    _cumulative_engine1_recovery_um,
    _derive_assessment_baseline_um,
)


def cumulative_posture_plus_cm(user) -> float:
    """Total Engine-1 (Posture+) recovery applied to date, in cm."""
    return round(_cumulative_engine1_recovery_um(user) / 10000.0, 6)


def starting_posture_loss_cm(user) -> float | None:
    """
    Assessment baseline total recoverable posture loss (cm) before any recovery.
    """
    state, _ = PostureState.objects.get_or_create(user=user)
    baseline_um = _derive_assessment_baseline_um(user, state)
    if not baseline_um:
        return None
    total_um = sum(int(v or 0) for v in baseline_um.values())
    if total_um <= 0:
        recoverable_um = int(state.total_recoverable_loss_um or 0)
        if recoverable_um > 0:
            return round(recoverable_um / 10000.0, 6)
        return None
    return round(total_um / 10000.0, 6)


def height_loss_display_cm(user) -> dict:
    """
    Spec: height_loss = starting_posture_loss − cumulative_posture_plus (3 decimal places).
    """
    starting = starting_posture_loss_cm(user)
    posture_plus = cumulative_posture_plus_cm(user)
    if starting is None:
        runtime = get_user_runtime_state_snapshot(user) or {}
        segments_um = (
            int(runtime.get("spinal_current_loss_um") or 0)
            + int(runtime.get("collapse_current_loss_um") or 0)
            + int(runtime.get("pelvic_current_loss_um") or 0)
            + int(runtime.get("legs_current_loss_um") or 0)
        )
        remaining = round(segments_um / 10000.0, 3)
        return {
            "starting_cm": None,
            "posture_plus_cumulative_cm": round(posture_plus, 3),
            "remaining_cm": remaining,
        }
    remaining = round(max(0.0, starting - posture_plus), 3)
    return {
        "starting_cm": round(starting, 3),
        "posture_plus_cumulative_cm": round(posture_plus, 3),
        "remaining_cm": remaining,
    }
