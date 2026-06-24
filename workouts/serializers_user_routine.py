from rest_framework import serializers
from .models import UserRoutine, UserRoutineExercise, WorkoutEntry
from user_profile.models import UserProfile
from django.forms.models import model_to_dict
from utils.exercise_library import section6_display_copy_for_exercise
from utils.user_time import user_today


# class UserRoutineExerciseSerializer(serializers.ModelSerializer):
#     # id = serializers.IntegerField(source="exercise.id")
#     exercise_id = serializers.IntegerField(source="exercise.id")
#     name = serializers.CharField(source="exercise.name")
#     short_name = serializers.CharField(source="exercise.short_name")
#     category = serializers.CharField(source="exercise.category")
#     points = serializers.IntegerField(source="exercise.points")
#     image = serializers.SerializerMethodField()
#     description = serializers.CharField(source="exercise.description", allow_blank=True)

#     completed = serializers.SerializerMethodField()

#     class Meta:
#         model = UserRoutineExercise
#         fields = (
#             "id","exercise_id", "name", "short_name", "category", "points", "image",
#             "description", "order", "tier", "sets", "unit",  "qty_min",
#                     "qty_max","notes", "completed"
#         )

#     def get_image(self, obj):
#         return obj.exercise.photo.url if obj.exercise.photo else None

#     def get_completed(self, obj):
#         request = self.context.get("request")
#         if not request or not request.user.is_authenticated:
#             return False
#         today = timezone.localdate()
#         return WorkoutEntry.objects.filter(
#             session__user=request.user,
#             session__date=today,
#             exercise=obj.exercise
#         ).exists()


class UserRoutineExerciseSerializer(serializers.ModelSerializer):
    exercise_id = serializers.IntegerField(source="exercise.id")
    name = serializers.CharField(source="exercise.name")
    short_name = serializers.CharField(source="exercise.short_name")
    category = serializers.CharField(source="exercise.category")
    category_label = serializers.SerializerMethodField()
    points = serializers.IntegerField(source="exercise.points")

    image = serializers.SerializerMethodField()
    description = serializers.CharField(source="exercise.description", allow_blank=True)
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
    completed = serializers.SerializerMethodField()
    section6_display_copy = serializers.SerializerMethodField()
    tier_label = serializers.SerializerMethodField()
    seconds_per_rep = serializers.DecimalField(
        source="exercise.seconds_per_rep",
        max_digits=4,
        decimal_places=2,
        allow_null=True,
        read_only=True,
    )
    primary_timer_dosage = serializers.SerializerMethodField()
    # Item 1 (robust fix): serve dosage LIVE from the linked catalog prescription
    # (VariantExercise) instead of the frozen UserRoutineExercise snapshot, so
    # existing users see current catalog numbers (sets/reps/unit) without needing
    # a routine regeneration. Falls back to the stored row for legacy rows that
    # have no variant link.
    sets = serializers.SerializerMethodField()
    unit = serializers.SerializerMethodField()
    qty_min = serializers.SerializerMethodField()
    qty_max = serializers.SerializerMethodField()

    class Meta:
        model = UserRoutineExercise
        fields = (
            "id",
            "exercise_id",
            "name",
            "short_name",
            "category",
            "category_label",
            "points",
            "image",
            "description",
            "instruction_content",
            "instruction_steps",
            "instruction_methods",
            "safety_note",
            "instruction_lines",
            "order",
            "tier",
            "tier_label",
            "sets",
            "unit",
            "qty_min",
            "qty_max",
            "notes",
            "seconds_per_rep",
            "primary_timer_dosage",
            "completed",
            "section6_display_copy",
        )

    def get_image(self, obj):
        """
        Priority:
        1. VariantExercise gender image
        2. Fallback to Exercise photo
        """
        request = self.context.get("request")
        user = request.user if request else None
        profile = UserProfile.objects.get(user=user)
        profile_dict = model_to_dict(profile)
        gender = profile_dict["gender"]
        gender = gender.lower()


        ve = obj.variant_exercise
        # print(user)
        # print(gender)
        if ve:
            if gender == "female":
                if ve.image_female:
                    return ve.image_female.url
                if ve.image_male:
                    return ve.image_male.url
            else:
                if ve.image_male:
                    return ve.image_male.url
                if ve.image_female:
                    return ve.image_female.url

        if obj.exercise.photo:
            return obj.exercise.photo.url

        return None

    def get_instruction_lines(self, obj):
        return obj.exercise.get_instruction_lines()

    def get_completed(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        today = user_today(request.user)
        return WorkoutEntry.objects.filter(
            session__user=request.user,
            session__date=today,
            exercise=obj.exercise
        ).exists()

    def get_section6_display_copy(self, obj):
        return section6_display_copy_for_exercise(getattr(obj.exercise, "name", None))

    def get_category_label(self, obj):
        from workouts.exercise_display_labels import exercise_category_label

        routine_type = None
        try:
            routine_type = getattr(getattr(obj, "routine", None), "routine_type", None)
        except Exception:
            routine_type = None
        return exercise_category_label(obj.exercise, routine_type=routine_type)

    @staticmethod
    def _dosage_source(obj):
        """Canonical (sets, qty_min, qty_max, unit, notes) for this row.

        Prefer the live catalog prescription (VariantExercise) so catalog edits
        show up without regenerating routines; fall back to the stored
        UserRoutineExercise snapshot only when there is no variant link.
        """
        ve = getattr(obj, "variant_exercise", None)
        if ve is not None:
            return {
                "sets": ve.sets,
                "qty_min": ve.quantity_min,
                "qty_max": ve.quantity_max,
                "unit": ve.unit,
                # URE.notes is overwritten with the assignment label at generation
                # time, dropping the "per side"/"per leg" qualifier; VE.notes keeps it.
                "notes": ve.notes or obj.notes,
            }
        return {
            "sets": obj.sets,
            "qty_min": obj.qty_min,
            "qty_max": obj.qty_max,
            "unit": obj.unit,
            "notes": obj.notes,
        }

    def get_sets(self, obj):
        return self._dosage_source(obj)["sets"]

    def get_unit(self, obj):
        return self._dosage_source(obj)["unit"]

    def get_qty_min(self, obj):
        return self._dosage_source(obj)["qty_min"]

    def get_qty_max(self, obj):
        return self._dosage_source(obj)["qty_max"]

    def get_primary_timer_dosage(self, obj):
        from workouts.exercise_timer_display import format_primary_timer_dosage

        src = self._dosage_source(obj)
        note_src = (src["notes"] or "").lower()
        per_side = "per" in note_src
        per_side_word = "leg" if "leg" in note_src else "side"
        return format_primary_timer_dosage(
            sets=src["sets"],
            quantity_min=src["qty_min"],
            quantity_max=src["qty_max"],
            unit=src["unit"],
            per_side=per_side,
            per_side_word=per_side_word,
        )

    def get_tier_label(self, obj):
        mapping = {
            "core": "STANDARD",
            "rec": "RECOMMENDED",
            "beast": "BEAST MODE",
        }
        return mapping.get(str(obj.tier or "").lower(), str(obj.tier or "").upper() or "STANDARD")

class UserRoutineSerializer(serializers.ModelSerializer):
    exercises = UserRoutineExerciseSerializer(many=True, read_only=True)

    class Meta:
        model = UserRoutine
        fields = (
            "id", "routine_type", "created_at", "updated_at", "is_active", "exercises"
        )
