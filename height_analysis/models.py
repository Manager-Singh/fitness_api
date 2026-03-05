### height_analysis/models.py
from django.db import models
from django.contrib.auth.models import User
from django.conf import settings

class GeneticHeightEstimate(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="genetic_estimate")
    estimated_height_cm = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - EGH: {self.estimated_height_cm} cm"


class HeightGrowthProjection(models.Model):
    genetic_estimate = models.ForeignKey(
        GeneticHeightEstimate, on_delete=models.CASCADE, related_name="growth_projections"
    )
    current_age = models.IntegerField()
    current_height_cm = models.FloatField()
    age_range = models.CharField(max_length=20)
    annual_growth_percent = models.FloatField()
    estimated_annual_gain_cm = models.FloatField()
    estimated_daily_gain_cm = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.genetic_estimate.user.username} ({self.age_range})"
