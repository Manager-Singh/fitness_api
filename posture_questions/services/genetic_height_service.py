from typing import Dict, Any
from user_profile.models import UserProfile
from height_analysis.models import GeneticHeightEstimate, HeightGrowthProjection


class GeneticHeightService:
    """Service for handling genetic height calculations and projections"""
    
    @staticmethod
    def calculate_estimated_genetic_height(father_cm: float, mother_cm: float, gender: str) -> float:
        """Calculate estimated genetic height based on parent heights"""
        avg = (father_cm + mother_cm) / 2
        return round(avg + 6.5, 2) if gender.lower() == 'male' else round(avg - 6.5, 2)
    
    @staticmethod
    def get_or_create_genetic_estimate(user, profile_dict: Dict[str, Any]) -> GeneticHeightEstimate:
        """Get or create genetic height estimate for user"""
        try:
            genetic_estimate = GeneticHeightEstimate.objects.prefetch_related('growth_projections').get(user=user)
            return genetic_estimate
        except GeneticHeightEstimate.DoesNotExist:
            return GeneticHeightService._create_genetic_estimate(user, profile_dict)
    
    @staticmethod
    def _create_genetic_estimate(user, profile_dict: Dict[str, Any]) -> GeneticHeightEstimate:
        """Create new genetic height estimate"""
        try:
            father_cm = float(profile_dict.get("father_height_cm") or 0)
            mother_cm = float(profile_dict.get("mother_height_cm") or 0)
            gender = (profile_dict.get("gender") or "").strip().lower()
            current_age = int(profile_dict.get("age") or 0)
            current_height = float(profile_dict.get("current_height_cm") or 0)
        except (ValueError, TypeError):
            raise ValueError("Invalid data in profile for genetic calculation.")

        estimated_height = GeneticHeightService.calculate_estimated_genetic_height(
            father_cm, mother_cm, gender
        )

        genetic_estimate = GeneticHeightEstimate.objects.create(
            user=user,
            estimated_height_cm=estimated_height
        )

        # Create growth projections
        GeneticHeightService._create_growth_projections(
            genetic_estimate, gender, current_age, current_height, estimated_height
        )
        
        return genetic_estimate
    
    @staticmethod
    def _create_growth_projections(genetic_estimate, gender: str, current_age: int, 
                                   current_height: float, estimated_height: float):
        """Create growth projections based on age and gender"""
        if gender == "male":
            age_check = 21
            growth_brackets = [
                (13, 14, 0.036), (14, 15, 0.026), (15, 16, 0.019), (16, 17, 0.0155),
                (17, 18, 0.011), (18, 19, 0.0075), (19, 20, 0.003), (20, 21, 0.002),
            ]
        else:
            age_check = 17
            growth_brackets = [
                (13, 14, 0.0225), (14, 15, 0.0125), (15, 16, 0.004), (16, 17, 0.001),
            ]

        if current_age and current_height:
            if current_age > age_check:
                HeightGrowthProjection.objects.create(
                    genetic_estimate=genetic_estimate,
                    current_age=current_age,
                    current_height_cm=current_height,
                    age_range="21+",
                    annual_growth_percent=0.0,
                    estimated_annual_gain_cm=0.0,
                    estimated_daily_gain_cm=0.0,
                )
            else:
                for min_age, max_age, percent in growth_brackets:
                    if min_age <= current_age < max_age:
                        gain_cm = estimated_height * percent
                        HeightGrowthProjection.objects.create(
                            genetic_estimate=genetic_estimate,
                            current_age=current_age,
                            current_height_cm=current_height,
                            age_range=f"{min_age}-{max_age}",
                            annual_growth_percent=percent,
                            estimated_annual_gain_cm=round(gain_cm, 2),
                            estimated_daily_gain_cm=round(gain_cm / 365, 4),
                        )
                        break
    
    @staticmethod
    def upsert_genetic_estimate(user, father_height: float, mother_height: float, 
                               gender: str, current_age: int, current_height: float) -> GeneticHeightEstimate:
        """Create or update genetic estimate with growth projections"""
        # If parents height not available
        if father_height is None or mother_height is None:
            estimated_height = current_height+2
        else:
            estimated_height = GeneticHeightService.calculate_estimated_genetic_height(
                father_height, mother_height, gender
            )

        genetic_estimate, _ = GeneticHeightEstimate.objects.update_or_create(
            user=user,
            defaults={'estimated_height_cm': estimated_height}
        )

        # Create growth projections
        growth_brackets = [
            (13, 14, 0.045, 0.0018),
            (14, 15, 0.0325, 0.0014),
            (15, 16, 0.0225, 0.0011),
            (16, 17, 0.0175, 0.0008),
            (17, 18, 0.0125, 0.0005),
            (18, 19, 0.0075, 0.0003),
            (19, 20, 0.003,  0.0002),
            (20, 21, 0.002,  0.0001),
        ]

        genetic_estimate.growth_projections.all().delete()

        if current_age > 21:
            HeightGrowthProjection.objects.create(
                genetic_estimate=genetic_estimate,
                current_age=current_age,
                current_height_cm=current_height,
                age_range="21+",
                annual_growth_percent=0.0,
                estimated_annual_gain_cm=0.0,
                estimated_daily_gain_cm=0.0,
            )
        else:
            for min_age, max_age, percent, _ in growth_brackets:
                if min_age <= current_age < max_age:
                    gain_cm = estimated_height * percent
                    HeightGrowthProjection.objects.create(
                        genetic_estimate=genetic_estimate,
                        current_age=current_age,
                        current_height_cm=current_height,
                        age_range=f"{min_age}-{max_age}",
                        annual_growth_percent=percent,
                        estimated_annual_gain_cm=round(gain_cm, 2),
                        estimated_daily_gain_cm=round(gain_cm / 365, 4),
                    )
                    break
        
        return genetic_estimate
