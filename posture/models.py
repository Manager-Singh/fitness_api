from django.db import models
from django.conf import settings

class PostureImage(models.Model):
    POSTURE_CHOICES = [
        ('front', 'Front'),
        ('side', 'Side'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posture_images')
    image = models.ImageField(upload_to='posture_images/')
    detected_type = models.CharField(max_length=10, choices=POSTURE_CHOICES)
    uploaded_type = models.CharField(max_length=10, choices=POSTURE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # New fields to store detailed posture analysis
    posture_score = models.FloatField(null=True, blank=True)
    pose_type = models.CharField(max_length=10, null=True, blank=True)
    details = models.JSONField(null=True, blank=True)  # JSON to store detailed information
    recommendations = models.JSONField(null=True, blank=True)  # JSON to store recommendations
    height_loss_inches = models.JSONField(null=True, blank=True) 


    def __str__(self):
        return f"{self.user.email} - {self.detected_type}"
    
    class Meta:
        verbose_name = "Posture Image"
        verbose_name_plural = "Posture Images"
        
        
class PostureReport(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posture_report')
    created_at = models.DateTimeField(auto_now_add=True)
    data = models.JSONField()  # Stores the full JSON (summary + optimization_breakdown)
    raw_request_data = models.JSONField(null=True, blank=True)
    t_pose_data = models.JSONField(null=True, blank=True)  # Stores the full JSON (Tpose)
    front_data = models.JSONField(null=True, blank=True)  # Stores the full JSON (Tpose)
    side_data = models.JSONField(null=True, blank=True)  # Stores the full JSON (Tpose)
    back_data = models.JSONField(null=True, blank=True)  # Stores the full JSON (Tpose)
    max_height_gain_inches = models.TextField(null=True, blank=True)


class PostureAssessment(models.Model):
    """Per-assessment event row; latest per source is is_active=True."""

    SOURCE_QUESTIONNAIRE = "questionnaire"
    SOURCE_SCAN = "scan"
    SOURCE_MOCK_SCAN = "mock_scan"
    SOURCE_CHOICES = [
        (SOURCE_QUESTIONNAIRE, "Questionnaire"),
        (SOURCE_SCAN, "Scan"),
        (SOURCE_MOCK_SCAN, "Mock Scan"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posture_assessments",
    )
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    spinal_loss_um = models.BigIntegerField()
    collapse_loss_um = models.BigIntegerField()
    pelvic_loss_um = models.BigIntegerField()
    legs_loss_um = models.BigIntegerField()
    total_loss_um = models.BigIntegerField()
    confidence_score = models.DecimalField(max_digits=3, decimal_places=2, default=1.00)
    is_active = models.BooleanField(default=True)
    completed_at = models.DateTimeField()
    raw_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "source", "is_active"]),
            models.Index(fields=["user", "-completed_at"]),
        ]
        verbose_name = "Posture Assessment"
        verbose_name_plural = "Posture Assessments"

    def __str__(self):
        return f"{self.user_id} {self.source} ({self.completed_at:%Y-%m-%d})"
