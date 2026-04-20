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
    trial_start = models.DateTimeField(null=True, blank=True)
    trial_end = models.DateTimeField(null=True, blank=True)
    account_tier = models.CharField(
        max_length=10,
        choices=[("teen", "Teen"), ("adult", "Adult")],
        null=True,
        blank=True,
    )
    transitioned_to_adult_at = models.DateTimeField(null=True, blank=True)
    timezone = models.CharField(max_length=80, default="UTC")
    last_reset_date = models.DateField(null=True, blank=True)
    display_name = models.CharField(max_length=255, null=True, blank=True)
    avatar_url = models.URLField(null=True, blank=True)

    
     
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


class Friendship(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
    ]

    user_id_a = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="friendships_sent",
    )
    user_id_b = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="friendships_received",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user_id_a", "user_id_b"],
                name="unique_friendship_pair",
            )
        ]

    def __str__(self):
        return f"{self.user_id_a_id}->{self.user_id_b_id} ({self.status})"


class FriendInvite(models.Model):
    inviter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_friend_invites",
    )
    invite_token = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    accepted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accepted_friend_invites",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.inviter_id}:{self.invite_token}"


class PostureState(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="posture_state",
    )
    scan_completed = models.BooleanField(default=False)
    questionnaire_completed = models.BooleanField(default=False)
    total_recoverable_loss_um = models.BigIntegerField(default=0)
    spinal_current_loss_um = models.BigIntegerField(default=0)
    collapse_current_loss_um = models.BigIntegerField(default=0)
    pelvic_current_loss_um = models.BigIntegerField(default=0)
    legs_current_loss_um = models.BigIntegerField(default=0)
    last_scan_at = models.DateTimeField(null=True, blank=True)
    algorithm_version = models.CharField(max_length=30, default="v1")
    updated_at = models.DateTimeField(auto_now=True)


class DailyLog(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="daily_logs",
    )
    log_date = models.DateField()
    exercise_points = models.IntegerField(default=0)
    food_points = models.IntegerField(default=0)
    lifestyle_points = models.IntegerField(default=0)
    engine1_points = models.IntegerField(default=0)
    engine2_points = models.IntegerField(default=0)
    diary_only_points = models.IntegerField(default=0)
    validated = models.BooleanField(default=False)
    streak_incremented = models.BooleanField(default=False)
    source_tz = models.CharField(max_length=80, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "log_date")
        ordering = ["-log_date"]


class HeightLedger(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="height_ledger",
    )
    log_date = models.DateField()
    entry_type = models.CharField(max_length=24)
    delta_um = models.BigIntegerField(default=0)
    cumulative_um = models.BigIntegerField(default=0)
    # Spec v3.2 (Section 13.4 / 14.1): Engine 2 uses 0.5 μm/pt. Store as integer
    # deci-micrometers (0.1 μm) to preserve precision (1 pt = 5 dμm).
    engine2_delta_dm = models.BigIntegerField(default=0)
    algorithm_version = models.CharField(max_length=30, default="v1")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-log_date", "-created_at"]


class NotificationEventLog(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notification_event_logs",
    )
    event_key = models.CharField(max_length=64)
    event_date = models.DateField()
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "event_key", "event_date")
        ordering = ["-event_date", "-created_at"]


@receiver(post_save, sender=User)
def _ensure_posture_state_on_signup(sender, instance, created, **kwargs):
    """
    Section 1.4 — ensure posture runtime state exists from account creation
    (scan_completed=false, zero loss until scan/questionnaire).
    """
    if created:
        PostureState.objects.get_or_create(user=instance)
