from django.contrib import admin

from .models import UltimateHeightPrediction


@admin.register(UltimateHeightPrediction)
class UltimateHeightPredictionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "band",
        "true_optimized_cm",
        "genetic_potential_cm",
        "posture_recovery_cm",
        "completed",
        "model_version",
        "computed_at",
    )
    list_filter = ("band", "completed", "model_version")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("computed_at",)
