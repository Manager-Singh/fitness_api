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
    points = serializers.IntegerField(required=False, min_value=0)
    set_index = serializers.IntegerField(required=False, min_value=1, write_only=True)
    completion_kind = serializers.CharField(required=False, allow_blank=True, write_only=True)
    client_timestamp = serializers.DateTimeField(required=False, write_only=True)

    class Meta:
        model = WorkoutEntry
        fields = (
            "exercise_id",
            "points",
            "sets_done",
            "reps_done",
            "duration_s",
            "set_index",
            "completion_kind",
            "client_timestamp",
        )


class WorkoutEntryReadSerializer(serializers.ModelSerializer):
    exercise_id = serializers.IntegerField(source="exercise.id")
    exercise = serializers.CharField(source="exercise.name")
    short_name = serializers.CharField(source="exercise.short_name", read_only=True)
    instruction_content = serializers.CharField(
        source="exercise.instruction_content", read_only=True, allow_blank=True
    )
    instruction_steps = serializers.JSONField(
        source="exercise.instruction_steps", read_only=True
    )
    instruction_methods = serializers.JSONField(
        source="exercise.instruction_methods", read_only=True
    )
    safety_note = serializers.CharField(source="exercise.safety_note", allow_blank=True, read_only=True)
    instruction_lines = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    completed_sets = serializers.SerializerMethodField()
    total_sets = serializers.SerializerMethodField()
    progress_fraction = serializers.SerializerMethodField()
    partially_completed = serializers.SerializerMethodField()
    exercise_completed = serializers.SerializerMethodField()

    class Meta:
        model = WorkoutEntry
        fields = (
            "id",
            "exercise_id",
            "exercise",
            "short_name",
            "instruction_content",
            "instruction_steps",
            "instruction_methods",
            "safety_note",
            "instruction_lines",
            "image",
            "points",
            "sets_done",
            "reps_done",
            "duration_s",
            "completed_sets",
            "total_sets",
            "progress_fraction",
            "partially_completed",
            "exercise_completed",
            "created_at",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        if user and getattr(user, "is_authenticated", False):
            from workouts.set_progress import progress_for_assignment

            ure = getattr(instance, "user_routine_exercise", None)
            if ure is not None:
                progress = progress_for_assignment(user, instance.session.date, ure)
                data.update(
                    {
                        "completed_sets": progress["completed_sets"],
                        "total_sets": progress["total_sets"],
                        "progress_fraction": progress["progress_fraction"],
                        "partially_completed": progress["partially_completed"],
                        "exercise_completed": progress["completed"],
                    }
                )
                return data
        data.update(
            {
                "completed_sets": instance.sets_done or 0,
                "total_sets": instance.sets_done or 0,
                "progress_fraction": 1.0 if instance.sets_done else 0.0,
                "partially_completed": False,
                "exercise_completed": bool(instance.sets_done),
            }
        )
        return data

    def get_instruction_lines(self, obj):
        if obj.exercise:
            return obj.exercise.get_instruction_lines()
        return []

    def get_image(self, obj):
        return obj.exercise.photo.url if obj.exercise and obj.exercise.photo else None

    def _progress(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        ure = getattr(obj, "user_routine_exercise", None)
        if user and getattr(user, "is_authenticated", False) and ure is not None:
            from workouts.set_progress import progress_for_assignment

            return progress_for_assignment(user, obj.session.date, ure)
        sets_done = int(obj.sets_done or 0)
        return {
            "completed_sets": sets_done,
            "total_sets": sets_done,
            "progress_fraction": 1.0 if sets_done else 0.0,
            "partially_completed": False,
            "completed": bool(sets_done),
        }

    def get_completed_sets(self, obj):
        return self._progress(obj)["completed_sets"]

    def get_total_sets(self, obj):
        return self._progress(obj)["total_sets"]

    def get_progress_fraction(self, obj):
        return self._progress(obj)["progress_fraction"]

    def get_partially_completed(self, obj):
        return self._progress(obj)["partially_completed"]

    def get_exercise_completed(self, obj):
        return self._progress(obj)["completed"]


class WorkoutSessionSerializer(serializers.ModelSerializer):
    entries = WorkoutEntryReadSerializer(many=True, read_only=True)
    user_routine_id = serializers.IntegerField(source="user_routine.id", read_only=True)

    class Meta:
        model = WorkoutSession
        fields = ("id", "date", "user_routine_id", "entries")
