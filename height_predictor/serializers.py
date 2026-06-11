"""Serializers for the Ultimate Height Predictor API (input validation + result shape)."""
from rest_framework import serializers

from .models import UltimateHeightPrediction


class UltimatePredictorInputSerializer(serializers.Serializer):
    """
    Validates the answers from the new question screens.

    Most fields are optional because:
      - onboarding values (sex, age, parent heights, current height) can be pulled server-side;
      - Band B skips the maturity questionnaire;
      - tape-measure + weight/shoe are explicitly optional (skipping is fine, no penalty).
    """

    # Core (optional here; the view fills any missing ones from the profile).
    sex = serializers.ChoiceField(choices=["male", "female"], required=False)
    age_years = serializers.FloatField(required=False, min_value=0, max_value=120)
    current_height_cm = serializers.FloatField(required=False, min_value=50, max_value=260)
    father_height_cm = serializers.FloatField(required=False, min_value=120, max_value=260)
    mother_height_cm = serializers.FloatField(required=False, min_value=120, max_value=260)

    # Maturity — MALE (Band A).
    voice_depth = serializers.IntegerField(required=False, min_value=0, max_value=2)
    facial_hair = serializers.IntegerField(required=False, min_value=0, max_value=2)
    body_hair = serializers.IntegerField(required=False, min_value=0, max_value=2)
    adams_apple = serializers.IntegerField(required=False, min_value=0, max_value=1)

    # Maturity — FEMALE (Band A).
    menarche_status = serializers.IntegerField(required=False, min_value=0, max_value=3)
    growth_spurt_status = serializers.IntegerField(required=False, min_value=0, max_value=2)

    # Both sexes.
    recent_growth_cm = serializers.FloatField(required=False, allow_null=True, min_value=0, max_value=40)

    # Optional tape measure.
    wingspan_cm = serializers.FloatField(required=False, allow_null=True, min_value=50, max_value=280)
    wrist_circumference_cm = serializers.FloatField(required=False, allow_null=True, min_value=8, max_value=30)

    # Optional refinement (analytics only).
    weight_kg = serializers.FloatField(required=False, allow_null=True, min_value=20, max_value=250)
    shoe_size = serializers.FloatField(required=False, allow_null=True, min_value=1, max_value=20)


class UltimatePredictionResultSerializer(serializers.ModelSerializer):
    """Server-authoritative result returned to the app (and read by the dashboard fallback)."""

    class Meta:
        model = UltimateHeightPrediction
        fields = [
            "id",
            "completed",
            "band",
            "model_version",
            "true_optimized_cm",
            "genetic_potential_cm",
            "posture_recovery_cm",
            "breakdown",
            "computed_at",
        ]
        read_only_fields = fields
