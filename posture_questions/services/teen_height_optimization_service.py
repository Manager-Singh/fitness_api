from typing import Dict, Any, Optional
from user_profile.models import UserProfile
from utils.teen_optimized_height import compute_optimized_height
from utils.posture.teen_profile_mapper import map_userprofile_to_teenprofile


class TeenHeightOptimizationService:
    """Service for teen height optimization calculations"""

    @staticmethod
    def get_optimized_height(profile: UserProfile, is_paid: bool, 
                            posture_breakdown: Dict[str, Any]) -> Optional[float]:
        """Calculate optimized height for paid teens (13-20 years old)
        
        Args:
            profile: User profile instance
            is_paid: Whether user has paid subscription
            posture_breakdown: Posture optimization breakdown data
            
        Returns:
            Optional[float]: Optimized height in cm if applicable, None otherwise
        """
        age = int(profile.age_years)
        
        # Only compute for paid teens aged 13-20
        if not (is_paid and 13 <= age <= 20):
            return None
        
        # Map profile to teen profile format
        teen_profile = map_userprofile_to_teenprofile(profile, posture_breakdown)
        
        # Run advanced model
        optimized_result = compute_optimized_height(teen_profile)
        
        return optimized_result["optimized_height_cm"]

    @staticmethod
    def should_calculate_optimization(age: int, is_paid: bool) -> bool:
        """Check if optimization should be calculated for user"""
        return is_paid and 13 <= age <= 20
