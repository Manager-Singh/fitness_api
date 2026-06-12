from rest_framework import serializers

from habits.models import MicroHabit, MicroHabitLog


class MicroHabitSerializer(serializers.ModelSerializer):
    instruction_steps = serializers.SerializerMethodField()
    instruction_lines = serializers.SerializerMethodField()

    class Meta:
        model = MicroHabit
        fields = (
            "code",
            "name",
            "ui_prompt",
            "how_to_detail",
            "instruction_steps",
            "instruction_lines",
            "image",
            "daily_max_points",
            "logging_mode",
            "points_per_log",
            "sort_order",
        )

    def get_instruction_steps(self, obj):
        return obj.get_instruction_steps()

    def get_instruction_lines(self, obj):
        return obj.get_instruction_lines()


class HabitLogWriteSerializer(serializers.Serializer):
    habit_code = serializers.SlugField()
    slot = serializers.ChoiceField(choices=["am", "pm", "once"])
    client_timestamp = serializers.DateTimeField(required=False)
