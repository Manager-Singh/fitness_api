from django import forms

from habits.models import MicroHabit
from workouts.widgets import InstructionStepsArrayWidget


class MicroHabitAdminForm(forms.ModelForm):
    """Admin form with Add more / Remove UI for instruction_steps."""

    class Meta:
        model = MicroHabit
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["instruction_steps"].widget = InstructionStepsArrayWidget()
