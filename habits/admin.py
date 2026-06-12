from django.contrib import admin
from django.utils.html import format_html

from habits.forms import MicroHabitAdminForm
from habits.models import MicroHabit, MicroHabitLog


@admin.register(MicroHabit)
class MicroHabitAdmin(admin.ModelAdmin):
    form = MicroHabitAdminForm
    list_display = (
        "sort_order",
        "code",
        "name",
        "image_thumb",
        "logging_mode",
        "daily_max_points",
        "points_per_log",
        "is_active",
    )
    list_filter = ("logging_mode", "is_active")
    search_fields = ("code", "name")
    ordering = ("sort_order", "name")
    readonly_fields = ("image_preview",)
    fields = (
        "code",
        "name",
        "ui_prompt",
        "how_to_detail",
        "instruction_steps",
        "image",
        "image_preview",
        "daily_max_points",
        "logging_mode",
        "points_per_log",
        "sort_order",
        "is_active",
    )

    @admin.display(description="Image")
    def image_thumb(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:40px;border-radius:6px;object-fit:cover;" />',
                obj.image.url,
            )
        return "—"

    @admin.display(description="Preview")
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height:180px;border-radius:8px;" />',
                obj.image.url,
            )
        return "No image uploaded yet."


@admin.register(MicroHabitLog)
class MicroHabitLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "log_date", "habit", "slot", "points", "logged_at")
    list_filter = ("log_date", "habit", "slot")
    search_fields = ("user__email", "user__username", "habit__code")
    readonly_fields = ("logged_at",)
