# accounts/models.py or your_main_app/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.dispatch import receiver
from django.db.models.signals import post_save
import secrets
import datetime

class User(AbstractUser):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('admin', 'Admin')
    ]

    # Make first_name and last_name optional
    name = models.CharField(max_length=150, blank=True, null=True)
    first_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)

    # Additional custom fields
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    device_id = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(unique=True)
    profile_step = models.CharField(max_length=20, blank=True, null=True)
    social_id = models.CharField(max_length=128, null=True, blank=True, unique=True)
    social_type = models.CharField(max_length=20, null=True, blank=True)
    profile_image_url = models.URLField(null=True, blank=True)
    social_auth_code = models.CharField(max_length=255, null=True, blank=True)
    verified = models.DateTimeField(null=True, blank=True)
    fcm_token= models.TextField(blank=True, null=True)
     
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']  # username still exists but email is used for login

    def __str__(self):
        return self.email
    
class OTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=4)  # changed from 6 to 4
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_valid(self):
        return timezone.now() < self.expires_at

    def __str__(self):
        return f"OTP for {self.user.email}"
