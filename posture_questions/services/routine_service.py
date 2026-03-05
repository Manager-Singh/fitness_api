from typing import Dict, Any
from workouts.models import UserRoutine
from utils.routine_genrate import generate_user_routines


class RoutineService:
    """Service for managing user workout routines"""

    @staticmethod
    def ensure_active_routine(user, optimization_breakdown: Dict[str, Any]) -> bool:
        """Ensure user has an active routine, create if needed
        
        Returns:
            bool: True if routine was created, False if already exists
        """
        has_active_routine = UserRoutine.objects.filter(
            user=user,
            is_active=True
        ).exists()
        
        if not has_active_routine:
            generate_user_routines(user, optimization_breakdown)
            return True
        
        return False

    @staticmethod
    def has_active_routine(user) -> bool:
        """Check if user has an active routine"""
        return UserRoutine.objects.filter(
            user=user,
            is_active=True
        ).exists()
