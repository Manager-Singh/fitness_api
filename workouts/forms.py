from django import forms

from .models import Exercise
from .widgets import InstructionStepsArrayWidget, InstructionMethodsWidget


class ExerciseAdminForm(forms.ModelForm):
    """Exercise change form: friendly instruction steps UI; legacy plain text not editable here."""

    class Meta:
        model = Exercise
        exclude = ("instruction_content",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["instruction_methods"].widget = InstructionMethodsWidget()
