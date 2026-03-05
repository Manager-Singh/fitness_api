from django.db import models
from django.contrib.auth.models import User
import json
from django.conf import settings  # Import settings to access AUTH_USER_MODEL

class PostureQuestion(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posture_questions')
    
    # Forward Head Posture
    forward_head_posture_question = models.TextField(max_length=255, null=True, blank=True)
    forward_head_posture_options = models.TextField(null=True, blank=True)
    forward_head_posture_answer = models.TextField(null=True, blank=True)  # JSON stored as text
 
    gap_between_your_lower_back_question = models.TextField(null=True, blank=True)
    gap_between_your_lower_back_options = models.TextField(null=True, blank=True)
    gap_between_your_lower_back_answer = models.TextField(null=True, blank=True)
    
    tightness_or_discomfort_question = models.TextField(null=True, blank=True)
    tightness_or_discomfort_options = models.TextField(null=True, blank=True)
    tightness_or_discomfort_answer = models.TextField(null=True, blank=True)
    
    slouch_when_standing_or_sitting_question = models.TextField(null=True, blank=True)
    slouch_when_standing_or_sitting_options = models.TextField(null=True, blank=True)
    slouch_when_standing_or_sitting_answer = models.TextField(null=True, blank=True)
    
    feel_noticeably_shorter_end_of_day_compare_to_morning_question = models.TextField(null=True, blank=True)
    feel_noticeably_shorter_end_of_day_compare_to_morning_options = models.TextField(null=True, blank=True)
    feel_noticeably_shorter_end_of_day_compare_to_morning_answer = models.TextField(null=True, blank=True)
    
    perfectly_aligned_and_decompressed_question = models.TextField(null=True, blank=True)
    perfectly_aligned_and_decompressed_options = models.TextField(null=True, blank=True)
    perfectly_aligned_and_decompressed_answer = models.TextField(null=True, blank=True)
    
    flexible_in_your_hamstrings_and_hips_question = models.TextField(null=True, blank=True)
    flexible_in_your_hamstrings_and_hips_options = models.TextField(null=True, blank=True)
    flexible_in_your_hamstrings_and_hips_answer = models.TextField(null=True, blank=True)
    
    active_your_core_during_daily_task_question = models.TextField(null=True, blank=True)
    active_your_core_during_daily_task_options = models.TextField(null=True, blank=True)
    active_your_core_during_daily_task_answer = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"