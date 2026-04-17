from django.db import models
from django.contrib.auth.models import User
import json
from django.conf import settings  # Import settings to access AUTH_USER_MODEL
from payment_packages.models import PaymentPackage





class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    # Personal Information
    language = models.CharField(max_length=100, null=True, blank=True)
    gender = models.CharField(max_length=100, null=True, blank=True)
    age = models.CharField(max_length=255, null=True, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    ethnicity = models.CharField(max_length=100, null=True, blank=True)
    
    # Height fields
    current_height_foot = models.CharField(max_length=255, null=True, blank=True)
    current_height_inch = models.CharField(max_length=255, null=True, blank=True)
    current_height_cm = models.CharField(max_length=255, null=True, blank=True)
    # Section 2 — canonical Base_Height from onboarding; immutable once set.
    base_height_cm = models.CharField(max_length=255, null=True, blank=True)
    current_height_type = models.CharField(max_length=20, null=True, blank=True)
    
    ideal_height_foot = models.CharField(max_length=255, null=True, blank=True)
    ideal_height_inch = models.CharField(max_length=255, null=True, blank=True)
    ideal_height_cm = models.CharField(max_length=255, null=True, blank=True)
    ideal_height_type = models.CharField(max_length=20, null=True, blank=True)
    
    father_height_foot = models.CharField(max_length=255, null=True, blank=True)
    father_height_inch = models.CharField(max_length=255, null=True, blank=True)
    father_height_cm = models.CharField(max_length=255, null=True, blank=True)
    father_height_type = models.CharField(max_length=20, null=True, blank=True)
    
    mother_height_foot = models.CharField(max_length=255, null=True, blank=True)
    mother_height_inch = models.CharField(max_length=255, null=True, blank=True)
    mother_height_cm = models.CharField(max_length=255, null=True, blank=True)
    mother_height_type = models.CharField(max_length=20, null=True, blank=True)
    
    # Activity and lifestyle
    activity_level_question = models.TextField(null=True, blank=True)
    activity_level_answer = models.TextField(null=True, blank=True)
    activity_level_all_option = models.TextField(null=True, blank=True)  # JSON stored as text
    
    sitting_hours_question = models.TextField(null=True, blank=True)
    sitting_hours_options = models.TextField(null=True, blank=True)
    sitting_hours_answer = models.TextField(null=True, blank=True)
    
    # Posture and flexibility
    posture_and_flexibility_question_one = models.TextField(null=True, blank=True)
    posture_and_flexibility_answer_one = models.TextField(null=True, blank=True)
    posture_and_flexibility_question_one_all_option = models.TextField(null=True, blank=True)
    
    posture_and_flexibility_question_two = models.TextField(null=True, blank=True)
    posture_and_flexibility_answer_two = models.TextField(null=True, blank=True)
    posture_and_flexibility_question_two_all_option = models.TextField(null=True, blank=True)
    
    posture_and_flexibility_question_three = models.TextField(null=True, blank=True)
    posture_and_flexibility_answer_three = models.TextField(null=True, blank=True)
    posture_and_flexibility_question_three_all_option = models.TextField(null=True, blank=True)
    
    # Sleep
    sleep_quality_and_position_question_one = models.TextField(null=True, blank=True)
    sleep_quality_and_position_answer_one = models.TextField(null=True, blank=True)
    
    sleep_quality_and_position_question_two = models.TextField(null=True, blank=True)
    sleep_quality_and_position_answer_two = models.TextField(null=True, blank=True)
    sleep_quality_and_position_question_two_all_option = models.TextField(null=True, blank=True)
    current_weight = models.TextField(null=True, blank=True)
    current_weight_lbs = models.TextField(null=True, blank=True)
    shoe_size = models.TextField(null=True, blank=True)
    shoe_size_eu = models.TextField(null=True, blank=True)
    
    sleep_hours_question = models.TextField(null=True, blank=True)
    sleep_hours_options = models.TextField(null=True, blank=True)
    sleep_hours_answer = models.TextField(null=True, blank=True)
     
    touch_toes_wt_bending_knees_question = models.TextField(null=True, blank=True)
    touch_toes_wt_bending_knees_options = models.TextField(null=True, blank=True)
    touch_toes_wt_bending_knees_answer = models.TextField(null=True, blank=True)
    
    discomfort_in_body_during_movement_question = models.TextField(null=True, blank=True)
    discomfort_in_body_during_movement_options = models.TextField(null=True, blank=True)
    discomfort_in_body_during_movement_answer = models.TextField(null=True, blank=True)
    
    main_goal_with_heightmax_question = models.TextField(null=True, blank=True)
    main_goal_with_heightmax_options = models.TextField(null=True, blank=True)
    main_goal_with_heightmax_answer = models.TextField(null=True, blank=True)
    last_scan = models.DateTimeField(null=True, blank=True)
    g_p_height_change = models.TextField(null=True, blank=True)
    g_p_shoe_pant_growth = models.TextField(null=True, blank=True)
    g_p_voice_stage = models.TextField(null=True, blank=True)
    g_p_facial_armpit_hair = models.TextField(null=True, blank=True)
    g_p_looks = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"

class ProfileType(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile_type') 
    activity_level_type = models.TextField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username}'s Profile Type"

class Payment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments') 
    package = models.ForeignKey(PaymentPackage, on_delete=models.CASCADE, related_name='paymentpackage') 
    payment_id = models.CharField(max_length=255)
    payment_status = models.CharField(max_length=100, null=True, blank=True)
    payment_method = models.CharField(max_length=100, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default='usd')
    complete_response = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Payment {self.payment_id} by {self.user.username}"