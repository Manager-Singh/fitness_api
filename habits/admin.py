from django.contrib import admin

from habits.models import MicroHabit, MicroHabitLog


@admin.register(MicroHabit)
class MicroHabitAdmin(admin.ModelAdmin):
    list_display = (
        "sort_order",
        "code",
        "name",
        "logging_mode",
        "daily_max_points",
        "points_per_log",
        "is_active",
    )
    list_filter = ("logging_mode", "is_active")
    search_fields = ("code", "name")
    ordering = ("sort_order", "name")


@admin.register(MicroHabitLog)
class MicroHabitLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "log_date", "habit", "slot", "points", "logged_at")
    list_filter = ("log_date", "habit", "slot")
    search_fields = ("user__email", "user__username", "habit__code")
    readonly_fields = ("logged_at",)
