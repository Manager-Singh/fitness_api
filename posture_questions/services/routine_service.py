import logging
from typing import Dict, Any, Optional

from django.core.exceptions import ValidationError

from workouts.models import UserRoutine
from utils.routine_genrate import generate_user_routines
from utils.posture.state_to_breakdown import posture_state_to_optimization_breakdown
from users.models import PostureState

logger = logging.getLogger(__name__)


class RoutineService:
    """Service for managing user workout routines"""

    @staticmethod
    def reconciled_optimization_breakdown(
        user,
        fallback_breakdown: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Prefer blended PostureState; fall back to caller-provided breakdown."""
        state = PostureState.objects.filter(user=user).first()
        if state and int(state.spinal_current_loss_um or 0) + int(state.collapse_current_loss_um or 0) > 0:
            return posture_state_to_optimization_breakdown(state)
        return fallback_breakdown or {}

    @staticmethod
    def ensure_active_routine(
        user,
        optimization_breakdown: Dict[str, Any],
        section3_contract: Dict[str, Any] | None = None,
    ) -> bool:
        """Ensure user has an active routine, create if needed
        
        Returns:
            bool: True if routine was created, False if already exists
        """
        has_active_routine = UserRoutine.objects.filter(
            user=user,
            is_active=True
        ).exists()
        
        if not has_active_routine:
            breakdown = RoutineService.reconciled_optimization_breakdown(
                user, optimization_breakdown
            )
            try:
                generate_user_routines(
                    user,
                    breakdown,
                    section3_contract=section3_contract,
                )
            except ValidationError as exc:
                logger.warning(
                    "Routine generation skipped: %s",
                    exc,
                    extra={"user_id": getattr(user, "id", None)},
                )
                return False
            return True

        return False

    @staticmethod
    def has_active_routine(user) -> bool:
        """Check if user has an active routine"""
        return UserRoutine.objects.filter(
            user=user,
            is_active=True
        ).exists()
