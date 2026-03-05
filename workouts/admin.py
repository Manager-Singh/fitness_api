# workouts/admin.py
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Exercise, AgeBracket,
    RoutineTemplate, RoutineVariant, VariantExercise,
    ExerciseCategory, Track, Tier,WorkoutSession,WorkoutEntry
)

# ──────────────────────────  EXERCISE  ──────────────────────────
@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display   = ("name","short_name", "category", "points", "thumb")
    list_filter    = ("category",)
    list_editable  = ("category", "points")
    search_fields  = ("name",)
    readonly_fields = ("thumb",)
    fields = (
        "name","short_name", "description",
        ("category", "points"),
        "photo", "thumb",
    )

    def thumb(self, obj):
        """Small preview in list & form pages."""
        if obj.photo:
            return format_html('<img src="{}" style="height:60px" />', obj.photo.url)
        return "—"
    thumb.short_description = "Preview"


# ──────────────────────────  AGE BRACKET  ───────────────────────
@admin.register(AgeBracket)
class AgeBracketAdmin(admin.ModelAdmin):
    list_display  = ("title", "min_age", "max_age")
    ordering      = ("min_age",)
    search_fields = ("title",)


# ───────────────────  TEMPLATE  →  VARIANT Inline  ──────────────
class VariantInline(admin.TabularInline):
    model               = RoutineVariant
    extra               = 0
    autocomplete_fields = ("age_bracket",)
    show_change_link    = True
    fields              = ("age_bracket", "track", "notes")


@admin.register(RoutineTemplate)
class RoutineTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "variant_count")
    inlines      = (VariantInline,)

    def variant_count(self, obj):
        return obj.variants.count()
    variant_count.short_description = "# Variants"


# ─────────────────────  VARIANT  →  EXERCISE Inline  ────────────
# class VariantExerciseInline(admin.TabularInline):
#     model               = VariantExercise
#     extra               = 1
#     autocomplete_fields = ("exercise",)
#     ordering            = ("order",)
#     fields = (
#         "order", "tier",
#         "exercise","type", "sets",
#         "quantity_min", "quantity_max", "unit",
#         "notes",
#     )

class VariantExerciseInline(admin.TabularInline):
    model = VariantExercise
    extra = 1
    autocomplete_fields = ("exercise",)
    ordering = ("order",)

    readonly_fields = ("male_thumb", "female_thumb")

    fields = (
        "order", "tier",
        "exercise", "type", "sets",
        "quantity_min", "quantity_max", "unit",
        "image_male", "image_female",
        "male_thumb", "female_thumb",
        "notes",
    )

    def male_thumb(self, obj):
        if obj.image_male:
            return format_html(
                '<img src="{}" style="height:50px;border-radius:6px;" />',
                obj.image_male.url
            )
        return "—"

    def female_thumb(self, obj):
        if obj.image_female:
            return format_html(
                '<img src="{}" style="height:50px;border-radius:6px;" />',
                obj.image_female.url
            )
        return "—"

    male_thumb.short_description = "♂"
    female_thumb.short_description = "♀"

@admin.register(RoutineVariant)
class RoutineVariantAdmin(admin.ModelAdmin):
    list_display  = ("template", "age_bracket", "track", "exercise_count")
    list_filter   = ("template", "age_bracket", "track")
    search_fields = ("template__name", "age_bracket__title")
    inlines       = (VariantExerciseInline,)

    def exercise_count(self, obj):
        return obj.prescriptions.count()
    exercise_count.short_description = "# Exercises"


# ─────────────────────────  STAND-ALONE  ────────────────────────
# @admin.register(VariantExercise)
# class VariantExerciseAdmin(admin.ModelAdmin):
#     list_display        = (
#         "variant", "order", "tier",
#         "exercise","type", "sets",
#         "quantity_min", "quantity_max", "unit",
#     )
#     list_filter         = ("tier", "unit", "variant__template")
#     autocomplete_fields = ("variant", "exercise")
#     ordering            = ("variant", "order")

class VariantExerciseAdmin(admin.ModelAdmin):
    list_display = (
        "variant", "order", "tier",
        "exercise", "type", "sets",
        "quantity_min", "quantity_max", "unit",
        "male_thumb", "female_thumb",
    )

    list_filter = ("tier", "unit", "variant__template")
    autocomplete_fields = ("variant", "exercise")
    ordering = ("variant", "order")

    readonly_fields = ("male_thumb", "female_thumb")

    fields = (
        "variant", "order", "tier",
        "exercise", "type", "sets",
        ("quantity_min", "quantity_max", "unit"),
        ("image_male", "image_female"),
        ("male_thumb", "female_thumb"),
        "notes",
    )

    def male_thumb(self, obj):
        if obj.image_male:
            return format_html(
                '<img src="{}" style="height:60px;border-radius:6px;" />',
                obj.image_male.url
            )
        return "—"

    def female_thumb(self, obj):
        if obj.image_female:
            return format_html(
                '<img src="{}" style="height:60px;border-radius:6px;" />',
                obj.image_female.url
            )
        return "—"

    male_thumb.short_description = "Male Preview"
    female_thumb.short_description = "Female Preview"


class WorkoutEntryInline(admin.TabularInline):
    model  = WorkoutEntry
    extra  = 0
    readonly_fields = ("created_at",)

@admin.register(WorkoutSession)
class WorkoutSessionAdmin(admin.ModelAdmin):
    list_display  = ("user", "date")
    list_filter   = ("user", "date")  #  correct way
    inlines       = [WorkoutEntryInline]

    def get_routine_type(self, obj):
        return obj.user_routine.routine_type if obj.user_routine else None
    get_routine_type.short_description = "Routine Type"