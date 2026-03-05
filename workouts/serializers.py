
from rest_framework import serializers

from .models import (
    Exercise,
    AgeBracket,
    RoutineVariant,
    VariantExercise,
)

# ───────────────────────────  Exercise  ────────────────────────────
class ExerciseSerializer(serializers.ModelSerializer):
    category   = serializers.CharField(source="get_category_display")
    photo_url  = serializers.SerializerMethodField()

    class Meta:
        model  = Exercise
        fields = (
            "id", "name", "description",
            "category",       # human‑readable string
            "points",
            "photo_url",      # absolute URL or null
        )

    # ---------- helpers ----------
    def get_photo_url(self, obj):
        request = self.context.get("request")
        if obj.photo and request is not None:
            return request.build_absolute_uri(obj.photo.url)
        return None


# ────────────────────────  Age Bracket  ───────────────────────────
class AgeBracketSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AgeBracket
        fields = ("id", "title", "min_age", "max_age")


# ─────────────────────  Variant Exercise  ─────────────────────────
class VariantExerciseSerializer(serializers.ModelSerializer):
    exercise         = ExerciseSerializer(read_only=True)
    quantity_display = serializers.SerializerMethodField()

    class Meta:
        model  = VariantExercise
        fields = (
            "order", "tier",             # NEW
            "sets",
            "quantity_min", "quantity_max", "quantity_display",
            "unit", "notes",
            "exercise",
        )

    # ---------- helpers ----------
    def get_quantity_display(self, obj):
        return obj.quantity_display

    # accept either explicit numbers OR a single "quantity_display" like "20-30"
    def to_internal_value(self, data):
        validated = super().to_internal_value(data)

        raw = data.get("quantity_display")
        if raw:
            if "-" in raw:
                lo, hi = map(int, raw.split("-"))
                validated["quantity_min"] = lo
                validated["quantity_max"] = hi
            else:
                validated["quantity_min"] = int(raw)
                validated["quantity_max"] = None
        return validated

    def validate(self, attrs):
        qmin = attrs.get("quantity_min")
        qmax = attrs.get("quantity_max")
        if qmax is not None and qmax < qmin:
            raise serializers.ValidationError("quantity_max must be ≥ quantity_min.")
        return attrs


# ───────────────────────  Routine Variant  ────────────────────────
class RoutineVariantSerializer(serializers.ModelSerializer):
    track         = serializers.CharField(source="get_track_display")   # NEW
    age_bracket   = AgeBracketSerializer(read_only=True)
    template      = serializers.StringRelatedField()
    prescriptions = VariantExerciseSerializer(many=True, read_only=True)

    class Meta:
        model  = RoutineVariant
        fields = (
            "id", "template", "track",   # now includes track name
            "age_bracket", "notes",
            "prescriptions",
        )
