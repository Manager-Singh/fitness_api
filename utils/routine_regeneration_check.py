"""15% segment optimization delta check and partial routine regeneration."""
from __future__ import annotations

import logging

from utils.posture.height_constants import POSTURE_SEGMENT_MAX_LOSS_CM

logger = logging.getLogger(__name__)

REGEN_THRESHOLD_PCT = 15.0

_SNAPSHOT_TO_STATE = {
    "spinal_loss_um": ("spinal_current_loss_um", "spinal_compression"),
    "collapse_loss_um": ("collapse_current_loss_um", "posture_collapse"),
    "pelvic_loss_um": ("pelvic_current_loss_um", "pelvic_tilt_back"),
    "legs_loss_um": ("legs_current_loss_um", "leg_hamstring"),
}


def check_and_maybe_regenerate_routine(user, previous_state_snapshot: dict | None = None) -> bool:
    """
    Compare current PostureState to routine generation snapshot.
    Regenerate Rec+Beast if any segment optimization % shifted >= 15%.
    """
    from users.models import PostureState
    from workouts.models import UserRoutine

    state = PostureState.objects.filter(user=user).first()
    if not state:
        return False

    routine = (
        UserRoutine.objects.filter(user=user, is_active=True)
        .order_by("-created_at")
        .first()
    )
    if not routine:
        return False

    snapshot = previous_state_snapshot or routine.posture_snapshot_at_generation or {}
    if not snapshot:
        return False

    max_delta_pct = _max_segment_opt_delta_pct(snapshot, state)
    if max_delta_pct < REGEN_THRESHOLD_PCT:
        return False

    from utils.routine_genrate import generate_user_routines
    from utils.posture.state_to_breakdown import (
        posture_state_snapshot,
        posture_state_to_optimization_breakdown,
    )

    breakdown = posture_state_to_optimization_breakdown(state)
    generate_user_routines(
        user,
        breakdown,
        regen_rec_beast_only=True,
        existing_routine=routine,
    )
    new_snapshot = posture_state_snapshot(state)
    routine.posture_snapshot_at_generation = new_snapshot
    scan_score = dict(routine.scan_score or {})
    scan_score["routine_regenerated"] = True
    scan_score["regen_delta_pct"] = round(max_delta_pct, 2)
    routine.scan_score = scan_score
    routine.save(update_fields=["posture_snapshot_at_generation", "scan_score", "updated_at"])
    logger.info(
        "Routine partial regen for user %s (max_delta_pct=%.2f)",
        user.id,
        max_delta_pct,
    )
    return True


def _max_segment_opt_delta_pct(snapshot: dict, state) -> float:
    max_delta = 0.0
    for snap_key, (state_attr, breakdown_key) in _SNAPSHOT_TO_STATE.items():
        max_loss_cm = float(POSTURE_SEGMENT_MAX_LOSS_CM[breakdown_key])
        max_loss_um = int(round(max_loss_cm * 10000))
        if max_loss_um <= 0:
            continue
        old_loss = int(snapshot.get(snap_key, 0) or 0)
        new_loss = int(getattr(state, state_attr, 0) or 0)
        old_pct = (1.0 - old_loss / max_loss_um) * 100.0
        new_pct = (1.0 - new_loss / max_loss_um) * 100.0
        max_delta = max(max_delta, abs(new_pct - old_pct))
    return max_delta
