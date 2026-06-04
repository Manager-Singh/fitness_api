from django.contrib import admin
from django import forms
from .models import PaymentPackage
from payment_packages.duration_utils import (
    DURATION_COUNT_CHOICES,
    DURATION_UNIT_CHOICES,
    decode_duration,
    encode_duration,
)
import json


class PaymentPackageForm(forms.ModelForm):
    features_data = forms.CharField(widget=forms.HiddenInput(), required=False)
    duration_count = forms.TypedChoiceField(
        choices=DURATION_COUNT_CHOICES,
        coerce=int,
        label="Duration",
        help_text="Number from 1 to 12.",
    )
    duration_unit = forms.ChoiceField(
        choices=DURATION_UNIT_CHOICES,
        label="Period",
        help_text="Day, week, month, or year.",
    )

    class Meta:
        model = PaymentPackage
        exclude = ("features",)

    class Media:
        js = ("payment_packages/admin/js/features_inline.js",)
        css = {"all": ("payment_packages/admin/css/features_inline.css",)}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        count, unit = decode_duration(
            getattr(self.instance, "duration", None) if self.instance.pk else "3"
        )
        self.fields["duration_count"].initial = count
        self.fields["duration_unit"].initial = unit
        self.fields["duration"].widget = forms.HiddenInput()
        self.fields["duration"].required = False

        instance_features = getattr(self.instance, "features", None)
        if isinstance(instance_features, str):
            try:
                features_list = json.loads(instance_features)
            except Exception:
                features_list = []
        elif isinstance(instance_features, list):
            features_list = instance_features
        else:
            features_list = []

        self.fields["features_data"].initial = json.dumps(features_list)

    def save(self, commit=True):
        instance = super().save(commit=False)

        count = self.cleaned_data.get("duration_count")
        unit = self.cleaned_data.get("duration_unit")
        if count is None or not unit:
            count, unit = decode_duration(getattr(instance, "duration", None))
        instance.duration = encode_duration(count, unit)

        features = []
        for key, value in self.data.items():
            if key.startswith("feature_") and value.strip():
                features.append(value.strip())
        instance.features = features
        if commit:
            instance.save()
        return instance


@admin.register(PaymentPackage)
class PaymentPackageAdmin(admin.ModelAdmin):
    form = PaymentPackageForm
    list_display = ("name", "amount", "is_free", "duration_display", "created_at")
    list_filter = ("is_free",)
    search_fields = ("name", "description")

    @admin.display(description="Duration")
    def duration_display(self, obj):
        return obj.get_duration_display()
