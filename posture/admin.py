from django.contrib import admin

from posture.models import PostureAssessment, PostureImage, PostureReport


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
