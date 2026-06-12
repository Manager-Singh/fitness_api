from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse

from posture.models import PostureAssessment, PostureImage, PostureReport, PostureScanSettings


@admin.register(PostureScanSettings)
class PostureScanSettingsAdmin(admin.ModelAdmin):
    """Single admin page to enable/disable server-side MediaPipe image scan."""

    list_display = ("image_scan_enabled", "updated_at")
    fields = ("image_scan_enabled", "updated_at")
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not PostureScanSettings.objects.filter(pk=1).exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj, _ = PostureScanSettings.objects.get_or_create(
            pk=1, defaults={"image_scan_enabled": False}
        )
        return redirect(reverse("admin:posture_posturescansettings_change", args=[obj.pk]))


@admin.register(PostureAssessment)
class PostureAssessmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "source",
        "is_active",
        "total_loss_um",
        "confidence_score",
        "completed_at",
    )
    list_filter = ("source", "is_active")
    search_fields = ("user__email", "user__username")
    readonly_fields = ("created_at",)


admin.site.register(PostureImage)
admin.site.register(PostureReport)
