# from django.contrib import admin
# from .models import PaymentPackage

# @admin.register(PaymentPackage)
# class PaymentPackageAdmin(admin.ModelAdmin):
#     list_display = ('name', 'amount', 'duration', 'created_at')
#     list_filter = ('duration',)
#     search_fields = ('name', 'description')
from django.contrib import admin
from django import forms
from .models import PaymentPackage
import json

class PaymentPackageForm(forms.ModelForm):
    features_data = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = PaymentPackage
        exclude = ('features',)

    class Media:
        js = ('payment_packages/admin/js/features_inline.js',)
        css = {'all': ('payment_packages/admin/css/features_inline.css',)}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Load features as list
        instance_features = getattr(self.instance, 'features', None)
        if isinstance(instance_features, str):
            try:
                features_list = json.loads(instance_features)
            except:
                features_list = []
        elif isinstance(instance_features, list):
            features_list = instance_features
        else:
            features_list = []

        # Store JSON in hidden field for JS
        self.fields['features_data'].initial = json.dumps(features_list)

    def save(self, commit=True):
        instance = super().save(commit=False)
        features = []
        for key, value in self.data.items():
            if key.startswith('feature_') and value.strip():
                features.append(value.strip())
        instance.features = features
        if commit:
            instance.save()
        return instance


@admin.register(PaymentPackage)
class PaymentPackageAdmin(admin.ModelAdmin):
    form = PaymentPackageForm
    list_display = ('name', 'amount', 'is_free', 'duration', 'created_at')
    list_filter = ('is_free', 'duration')
    search_fields = ('name', 'description')
