"""
Storage for the Ultimate Height Predictor (Model v2).

Purely additive: this table only holds the new assessment's inputs + the produced number.
It does not alter any existing model and is never read by the daily-points / engine / ledger
systems. The dashboard reads the produced `true_optimized_cm` only through the single fallback
branch in posture_questions.views.
"""
from django.conf import settings
from django.db import models


class UltimateHeightPrediction(models.Model):
    """One row per completed (or attempted) Ultimate Predictor assessment. Latest = current."""

    BAND_A = "A"
    BAND_B = "B"
    BAND_ADULT = "20+"
    BAND_CHOICES = [
        (BAND_A, "Band A (13.0-17.49, full)"),
        (BAND_B, "Band B (17.5-20, lite)"),
        (BAND_ADULT, "20+ (posture only)"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ultimate_height_predictions",
    )

    # --- Inputs captured at assessment time (snapshot; onboarding values may change later) ---
    sex = models.CharField(max_length=10, blank=True, default="")
    age_years = models.FloatField(null=True, blank=True)
    current_height_cm = models.FloatField(null=True, blank=True)
    father_height_cm = models.FloatField(null=True, blank=True)
    mother_height_cm = models.FloatField(null=True, blank=True)

    # Maturity taps (male: voice/facial/body/adams; female: menarche/body/spurt).
    voice_depth = models.PositiveSmallIntegerField(default=0)
    facial_hair = models.PositiveSmallIntegerField(default=0)
    body_hair = models.PositiveSmallIntegerField(default=0)
    adams_apple = models.PositiveSmallIntegerField(default=0)
    menarche_status = models.PositiveSmallIntegerField(default=0)
    growth_spurt_status = models.PositiveSmallIntegerField(default=0)

    recent_growth_cm = models.FloatField(null=True, blank=True)

    # Optional tape measure (no penalty if skipped).
    wingspan_cm = models.FloatField(null=True, blank=True)
    wrist_circumference_cm = models.FloatField(null=True, blank=True)

    # Optional refinement (analytics only in v2).
    weight_kg = models.FloatField(null=True, blank=True)
    shoe_size = models.FloatField(null=True, blank=True)

    # --- Posture snapshot (READ from the existing PostureState; never recomputed here) ---
    posture_recovery_cm = models.FloatField(default=0.0)

    # --- Outputs ---
    genetic_potential_cm = models.FloatField(null=True, blank=True)
    true_optimized_cm = models.FloatField(null=True, blank=True)
    band = models.CharField(max_length=4, blank=True, default="", choices=BAND_CHOICES)
    model_version = models.CharField(max_length=10, blank=True, default="v2")

    completed = models.BooleanField(default=False)

    # Full inputs + breakdown JSON for Part 9 calibration / audit.
    raw_inputs = models.JSONField(default=dict, blank=True)
    breakdown = models.JSONField(default=dict, blank=True)

    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-computed_at"]
        indexes = [
            models.Index(fields=["user", "completed", "-computed_at"], name="hp_ultpred_user_done_idx"),
        ]

    def __str__(self):
        return f"UltimatePrediction(user={self.user_id}, {self.true_optimized_cm} cm, band={self.band})"
