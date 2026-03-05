# workouts/serializers_log.py
from rest_framework import serializers
from django.apps import apps

WorkoutSession = apps.get_model("workouts", "WorkoutSession")
WorkoutEntry   = apps.get_model("workouts", "WorkoutEntry")
Exercise       = apps.get_model("workouts", "Exercise")
UserRoutine    = apps.get_model("workouts", "UserRoutine")


class WorkoutEntryWriteSerializer(serializers.ModelSerializer):
    """
    Client POSTs a finished exercise.
    """
    exercise_id = serializers.PrimaryKeyRelatedField(
        queryset=Exercise.objects.all(), source="exercise"
    )

    class Meta:
        model = WorkoutEntry
        fields = ("exercise_id", "points", "sets_done", "reps_done", "duration_s")


class WorkoutEntryReadSerializer(serializers.ModelSerializer):
    exercise_id = serializers.IntegerField(source="exercise.id")
    exercise = serializers.CharField(source="exercise.name")
    short_name = serializers.CharField(source="exercise.short_name", read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = WorkoutEntry
        fields = (
            "id",
            "exercise_id",
            "exercise",
            "short_name",
            "image",
            "points",
            "sets_done",
            "reps_done",
            "duration_s",
            "created_at",
        )

    def get_image(self, obj):
        return obj.exercise.photo.url if obj.exercise and obj.exercise.photo else None


class WorkoutSessionSerializer(serializers.ModelSerializer):
    entries = WorkoutEntryReadSerializer(many=True, read_only=True)
    user_routine_id = serializers.IntegerField(source="user_routine.id", read_only=True)

    class Meta:
        model = WorkoutSession
        fields = ("id", "date", "user_routine_id", "entries")
