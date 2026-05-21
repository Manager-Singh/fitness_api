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

    def clean(self):
        cleaned = super().clean()
        pcts = [
            cleaned.get("spinal_pct"),
            cleaned.get("collapse_pct"),
            cleaned.get("pelvic_pct"),
            cleaned.get("legs_pct"),
        ]
        if all(p is not None for p in pcts):
            total = sum(int(p) for p in pcts)
            if total != 100:
                from django.core.exceptions import ValidationError

                raise ValidationError(
                    f"Segment percentages must sum to 100 (currently {total})."
                )
        return cleaned
