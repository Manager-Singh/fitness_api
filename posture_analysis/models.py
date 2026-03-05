from django.db import models
from django.contrib.auth.models import User
import json
from django.conf import settings  # Import settings to access AUTH_USER_MODEL

class UserPosturalOptimizationData(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_analysis')
    summary = models.TextField()
    max_height_gain_inches = models.FloatField()
    note = models.TextField()

    spinal_compression = models.PositiveSmallIntegerField()
    posture_collapse = models.PositiveSmallIntegerField()
    pelvic_tilt_back = models.PositiveSmallIntegerField()
    leg_hamstring = models.PositiveSmallIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class PosturalRecommendation(models.Model):
    user_data = models.ForeignKey(UserPosturalOptimizationData, on_delete=models.CASCADE, related_name='recommendations')
    title = models.CharField(max_length=255)
    description = models.TextField()
