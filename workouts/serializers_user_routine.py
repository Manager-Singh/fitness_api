from rest_framework import serializers
from django.utils import timezone
from .models import UserRoutine, UserRoutineExercise, WorkoutEntry
from user_profile.models import UserProfile
from django.forms.models import model_to_dict
from utils.exercise_library import section6_display_copy_for_exercise


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

    class Meta:
        model = UserRoutineExercise
        fields = (
            "id",
            "exercise_id",
            "name",
            "short_name",
            "category",
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
            "sets",
            "unit",
            "qty_min",
            "qty_max",
            "notes",
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

        today = timezone.localdate()
        return WorkoutEntry.objects.filter(
            session__user=request.user,
            session__date=today,
            exercise=obj.exercise
        ).exists()

    def get_section6_display_copy(self, obj):
        return section6_display_copy_for_exercise(getattr(obj.exercise, "name", None))

class UserRoutineSerializer(serializers.ModelSerializer):
    exercises = UserRoutineExerciseSerializer(many=True, read_only=True)

    class Meta:
        model = UserRoutine
        fields = (
            "id", "routine_type", "created_at", "updated_at", "is_active", "exercises"
        )
