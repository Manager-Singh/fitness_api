from rest_framework import serializers

from habits.models import MicroHabit, MicroHabitLog


class MicroHabitSerializer(serializers.ModelSerializer):
    class Meta:
        model = MicroHabit
        fields = (
            "code",
            "name",
            "ui_prompt",
            "daily_max_points",
            "logging_mode",
            "points_per_log",
            "sort_order",
        )


class HabitLogWriteSerializer(serializers.Serializer):
    habit_code = serializers.SlugField()
    slot = serializers.ChoiceField(choices=["am", "pm", "once"])
    client_timestamp = serializers.DateTimeField(required=False)
