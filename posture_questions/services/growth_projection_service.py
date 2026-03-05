from typing import Dict, Any, Optional
from height_analysis.models import GeneticHeightEstimate


class GrowthProjectionService:
    """Service for handling growth projection data"""

    @staticmethod
    def get_projection_data(genetic_estimate: GeneticHeightEstimate) -> Optional[Dict[str, Any]]:
        """Get first growth projection data"""
        first_projection = genetic_estimate.growth_projections.first()
        
        if not first_projection:
            return None
            
        return {
            'age_range': first_projection.age_range,
            'annual_growth_percent': first_projection.annual_growth_percent,
            'estimated_annual_gain_cm': first_projection.estimated_annual_gain_cm,
            'estimated_daily_gain_cm': first_projection.estimated_daily_gain_cm,
        }

    @staticmethod
    def calculate_genetic_status(current_cm: float, estimated_height: float) -> tuple:
        """Calculate genetic height difference and status
        
        Returns:
            tuple: (genetic_diff, genetic_status)
        """
        genetic_diff = round(current_cm - estimated_height, 2)
        
        if genetic_diff > 0:
            genetic_status = "above_estimated_genetic_height"
        elif genetic_diff < 0:
            genetic_status = "below_estimated_genetic_height"
        else:
            genetic_status = "at_estimated_genetic_height"
        
        return genetic_diff, genetic_status

    @staticmethod
    def calculate_mph_cm(dad_cm: Optional[float], mom_cm: Optional[float], gender: str) -> Optional[float]:
        """Calculate mid-parental height in cm"""
        if dad_cm is None or mom_cm is None:
            return None
            
        if gender.lower() == "male":
            return (dad_cm + mom_cm + 13) / 2
        else:
            return (dad_cm + mom_cm - 13) / 2
