import json

from django.contrib import admin, messages
from django.utils.html import format_html

from .models import UltimateHeightPrediction
from .services import compute_and_store_prediction


@admin.register(UltimateHeightPrediction)
class UltimateHeightPredictionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_link",
        "band",
        "true_optimized_cm",
        "genetic_potential_cm",
        "posture_recovery_cm",
        "completed",
        "model_version",
        "computed_at",
    )
    list_filter = ("band", "completed", "model_version")
    search_fields = ("user__username", "user__email", "user__id")
    raw_id_fields = ("user",)
    list_select_related = ("user",)
    readonly_fields = (
        "computed_at",
        "breakdown_pretty",
        "raw_inputs_pretty",
    )
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "user",
                    "completed",
                    "band",
                    "model_version",
                    "computed_at",
                )
            },
        ),
        (
            "Outputs",
            {
                "fields": (
                    "true_optimized_cm",
                    "genetic_potential_cm",
                    "posture_recovery_cm",
                )
            },
        ),
        (
            "Inputs snapshot",
            {
                "classes": ("collapse",),
                "fields": (
                    "sex",
                    "age_years",
                    "current_height_cm",
                    "father_height_cm",
                    "mother_height_cm",
                    "voice_depth",
                    "facial_hair",
                    "body_hair",
                    "adams_apple",
                    "menarche_status",
                    "growth_spurt_status",
                    "recent_growth_cm",
                    "wingspan_cm",
                    "wrist_circumference_cm",
                    "weight_kg",
                    "shoe_size",
                ),
            },
        ),
        (
            "Audit",
            {
                "classes": ("collapse",),
                "fields": ("raw_inputs_pretty", "breakdown_pretty"),
            },
        ),
    )
    actions = ("regenerate_from_profile",)

    @admin.display(description="User", ordering="user__email")
    def user_link(self, obj):
        from django.urls import reverse

        url = reverse("admin:users_user_change", args=[obj.user_id])
        return format_html('<a href="{}">{}</a>', url, obj.user)

    @admin.display(description="Breakdown (JSON)")
    def breakdown_pretty(self, obj):
        if not obj or not obj.breakdown:
            return "—"
        text = json.dumps(obj.breakdown, indent=2, sort_keys=True)
        return format_html("<pre style=\"max-height:400px;overflow:auto;\">{}</pre>", text)

    @admin.display(description="Raw inputs (JSON)")
    def raw_inputs_pretty(self, obj):
        if not obj or not obj.raw_inputs:
            return "—"
        text = json.dumps(obj.raw_inputs, indent=2, sort_keys=True)
        return format_html("<pre style=\"max-height:300px;overflow:auto;\">{}</pre>", text)

    @admin.action(description="Regenerate selected from user profile (+ prior maturity answers)")
    def regenerate_from_profile(self, request, queryset):
        ok = 0
        failed = 0
        for row in queryset.select_related("user"):
            prediction, err = compute_and_store_prediction(row.user, source="admin_regenerate")
            if prediction:
                ok += 1
            else:
                failed += 1
                missing = (err or {}).get("missing", [])
                self.message_user(
                    request,
                    f"Skipped {row.user.email}: missing {', '.join(missing) or 'required fields'}.",
                    level=messages.WARNING,
                )
        if ok:
            self.message_user(request, f"Generated {ok} prediction(s).", level=messages.SUCCESS)
