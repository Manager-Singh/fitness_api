"""
Workout-plan serializers
────────────────────────
• RoutinePlanSerializer — top-level plan sent to the mobile app
• ExerciseWorkoutSerializer — nested exercises with “completed” flag
"""

from django.apps import apps
from rest_framework import serializers
from utils.exercise_library import section6_display_copy_for_exercise
from utils.user_time import user_today

# ── lazy model look-ups (avoids circular imports) ───────────────────────
Exercise         = apps.get_model("workouts", "Exercise")
RoutineVariant   = apps.get_model("workouts", "RoutineVariant")
VariantExercise  = apps.get_model("workouts", "VariantExercise")


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
    instruction_content = serializers.CharField(
        source="exercise.instruction_content", allow_blank=True
    )
    instruction_steps = serializers.JSONField(
        source="exercise.instruction_steps", read_only=True
    )
    instruction_methods = serializers.JSONField(
        source="exercise.instruction_methods", read_only=True
    )
    safety_note = serializers.CharField(source="exercise.safety_note", allow_blank=True, read_only=True)
    instruction_lines = serializers.SerializerMethodField()

    # prescription-level fields
    sets     = serializers.IntegerField()
    order    = serializers.IntegerField()
    tier     = serializers.CharField()
    unit     = serializers.CharField()
    qty_min  = serializers.IntegerField(source="quantity_min")
    qty_max  = serializers.IntegerField(source="quantity_max", allow_null=True)

    # NEW ▶︎ has the user completed this exercise today?
    completed = serializers.SerializerMethodField()
    section6_display_copy = serializers.SerializerMethodField()
    seconds_per_rep = serializers.DecimalField(
        source="exercise.seconds_per_rep",
        max_digits=4,
        decimal_places=2,
        allow_null=True,
        read_only=True,
    )
    primary_timer_dosage = serializers.SerializerMethodField()
    completed_sets = serializers.SerializerMethodField()
    total_sets = serializers.SerializerMethodField()
    progress_fraction = serializers.SerializerMethodField()
    partially_completed = serializers.SerializerMethodField()
    is_unilateral = serializers.SerializerMethodField()
    unilateral_label = serializers.SerializerMethodField()
    switch_prompt_text = serializers.SerializerMethodField()
    switch_prompt_subtext = serializers.SerializerMethodField()
    switch_countdown_seconds = serializers.SerializerMethodField()
    credit_unit = serializers.SerializerMethodField()

    class Meta:
        model  = VariantExercise
        fields = (
            "id", "name","short_name", "points", "category", "image", "description",
            "instruction_content",
            "instruction_steps",
            "instruction_methods",
            "safety_note",
            "instruction_lines",
            "order", "tier",'type', "sets", "qty_min", "qty_max", "unit",
            "seconds_per_rep",
            "primary_timer_dosage",
            "completed",
            "completed_sets",
            "total_sets",
            "progress_fraction",
            "partially_completed",
            "is_unilateral",
            "unilateral_label",
            "switch_prompt_text",
            "switch_prompt_subtext",
            "switch_countdown_seconds",
            "credit_unit",
            "section6_display_copy",
        )

    # helper --------------------------------------------------------------
    def get_instruction_lines(self, obj):
        return obj.exercise.get_instruction_lines()

    def get_image(self, obj):
        photo = obj.exercise.photo
        return photo.url if photo else None 
    
    def get_completed(self, obj):
        """
        Return True if the request user has completed every credited set
        for *today* that matches this variant & exercise.
        """
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        progress = self._progress(obj, request.user, user_today(request.user))
        return progress["completed"]

    def _progress(self, obj, user, today):
        from workouts.set_progress import completed_set_count

        total_sets = max(1, int(obj.sets or 1))
        done = min(
            completed_set_count(user, today, exercise=obj.exercise),
            total_sets,
        )
        return {
            "completed_sets": done,
            "total_sets": total_sets,
            "progress_fraction": float(done / total_sets) if total_sets else 0.0,
            "partially_completed": bool(0 < done < total_sets),
            "completed": bool(done >= total_sets),
        }

    def get_completed_sets(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return 0
        return self._progress(obj, request.user, user_today(request.user))["completed_sets"]

    def get_total_sets(self, obj):
        return max(1, int(obj.sets or 1))

    def get_progress_fraction(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return 0.0
        return self._progress(obj, request.user, user_today(request.user))["progress_fraction"]

    def get_partially_completed(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return self._progress(obj, request.user, user_today(request.user))["partially_completed"]

    def get_section6_display_copy(self, obj):
        return section6_display_copy_for_exercise(getattr(obj.exercise, "name", None))

    def get_primary_timer_dosage(self, obj):
        from workouts.exercise_timer_display import format_primary_timer_dosage

        note_src = (obj.notes or "").lower()
        per_side = self._is_unilateral(obj) or "per" in note_src
        per_side_word = self._unilateral_label(obj) or ("leg" if "leg" in note_src else "side")
        return format_primary_timer_dosage(
            sets=obj.sets,
            quantity_min=obj.quantity_min,
            quantity_max=obj.quantity_max,
            unit=obj.unit,
            per_side=per_side,
            per_side_word=per_side_word,
        )

    def _is_unilateral(self, obj):
        if bool(getattr(obj, "is_unilateral", False)):
            return True
        note_src = str(getattr(obj, "notes", "") or "").lower()
        return any(token in note_src for token in ("per side", "per leg", "per arm", "each side", "each leg"))

    def _unilateral_label(self, obj):
        label = str(getattr(obj, "unilateral_label", "") or "").strip().lower()
        if label:
            return label
        note_src = str(getattr(obj, "notes", "") or "").lower()
        if "leg" in note_src:
            return "leg"
        if "arm" in note_src:
            return "arm"
        return "side" if self._is_unilateral(obj) else ""

    def get_is_unilateral(self, obj):
        return self._is_unilateral(obj)

    def get_unilateral_label(self, obj):
        return self._unilateral_label(obj)

    def get_switch_prompt_text(self, obj):
        if not self._is_unilateral(obj):
            return ""
        return "SWITCH LEGS" if self._unilateral_label(obj) == "leg" else "SWITCH SIDES"

    def get_switch_prompt_subtext(self, obj):
        if not self._is_unilateral(obj):
            return ""
        return (
            "Get into position on your other leg"
            if self._unilateral_label(obj) == "leg"
            else "Get into position on your other side"
        )

    def get_switch_countdown_seconds(self, obj):
        return 3 if self._is_unilateral(obj) else 0

    def get_credit_unit(self, obj):
        return "set"


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
