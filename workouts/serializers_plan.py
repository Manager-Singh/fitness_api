"""
Workout-plan serializers
────────────────────────
• RoutinePlanSerializer — top-level plan sent to the mobile app
• ExerciseWorkoutSerializer — nested exercises with “completed” flag
"""

from django.apps import apps
from django.utils import timezone
from rest_framework import serializers

# ── lazy model look-ups (avoids circular imports) ───────────────────────
Exercise         = apps.get_model("workouts", "Exercise")
RoutineVariant   = apps.get_model("workouts", "RoutineVariant")
VariantExercise  = apps.get_model("workouts", "VariantExercise")
WorkoutEntry     = apps.get_model("workouts", "WorkoutEntry")


# ─────────────────────────────────────────────────────────────────────────
#  NESTED  – one exercise inside a routine variant
# ─────────────────────────────────────────────────────────────────────────
class ExerciseWorkoutSerializer(serializers.ModelSerializer):
    # fields from Exercise
    id        = serializers.IntegerField(source="exercise.id")
    name      = serializers.CharField(source="exercise.name")
    short_name      = serializers.CharField(source="exercise.short_name")
    points    = serializers.IntegerField(source="exercise.points")
    category  = serializers.CharField(source="exercise.category")
    # ---- change this line ---------------------------
    image     = serializers.SerializerMethodField()      # ← was ImageField
    # -------------------------------------------------
    description = serializers.CharField(
        source="exercise.description", allow_blank=True
    )

    # prescription-level fields
    sets     = serializers.IntegerField()
    order    = serializers.IntegerField()
    tier     = serializers.CharField()
    unit     = serializers.CharField()
    qty_min  = serializers.IntegerField(source="quantity_min")
    qty_max  = serializers.IntegerField(source="quantity_max", allow_null=True)

    # NEW ▶︎ has the user completed this exercise today?
    completed = serializers.SerializerMethodField()

    class Meta:
        model  = VariantExercise
        fields = (
            "id", "name","short_name", "points", "category", "image", "description",
            "order", "tier",'type', "sets", "qty_min", "qty_max", "unit",
            "completed",
        )

    # helper --------------------------------------------------------------
    def get_image(self, obj):
        photo = obj.exercise.photo
        return photo.url if photo else None 
    
    def get_completed(self, obj):
        """
        Return True if the request user has at least one WorkoutEntry
        for *today* that matches this variant & exercise.
        """
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        today = timezone.localdate()
        return WorkoutEntry.objects.filter(
            session__user=request.user,
            session__date=today,
            session__routine_variant=obj.variant,
            exercise=obj.exercise,
        ).exists()


# ─────────────────────────────────────────────────────────────────────────
#  TOP-LEVEL  – routine variant with nested exercises
# ─────────────────────────────────────────────────────────────────────────
class RoutinePlanSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name")
    track         = serializers.CharField()
    age_group     = serializers.CharField(source="age_bracket.title")

    # pull prescriptions ⇒ nested exercises
    exercises = ExerciseWorkoutSerializer(
        source="prescriptions", many=True, read_only=True,
        context={"request": None},  # will be overwritten by DRF automatically
    )

    class Meta:
        model  = RoutineVariant
        fields = (
            "id", "template", "template_name",
            "track", "age_group",
            "exercises",
        )

    # ensure nested serializer gets the request object
    def to_representation(self, instance):
        # inject the same context (with request) into child serializer
        self.fields["exercises"].context.update(self.context)
        return super().to_representation(instance)
