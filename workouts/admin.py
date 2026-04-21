# workouts/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from django.contrib.admin import helpers
from django.contrib.admin.utils import get_deleted_objects
from django.template.response import TemplateResponse
from django.utils.translation import gettext_lazy as _

from .models import (
    Exercise, AgeBracket,
    RoutineTemplate, RoutineVariant, VariantExercise,
    ExerciseCategory, Track, Tier, WorkoutSession, WorkoutEntry,
    UserRoutine, RoutineType, UserRoutineExercise
)

from posture.models import PostureReport
from utils.posture.height_constants import POSTURE_SEGMENT_MAX_LOSS_CM, posture_segment_opt_pct
from utils.routine_genrate import generate_user_routines


def _default_breakdown():
    out = {}
    for seg, mx in POSTURE_SEGMENT_MAX_LOSS_CM.items():
        cur = round(float(mx) * 0.5, 2)
        out[seg] = {
            "current_loss_cm": cur,
            "max_loss_cm": mx,
            "percent_optimized": posture_segment_opt_pct(cur, mx),
        }
    return out


def _demo_scan_score_from_breakdown(breakdown: dict) -> dict:
    """
    Demo-friendly scan_score payload for admin tools.
    The real scan pipeline stores richer data in PostureReport; this is only
    to ensure routines have non-empty JSON fields for testing/UI rendering.
    """
    out = {}
    for seg in ("spinal_compression", "posture_collapse", "pelvic_tilt_back", "leg_hamstring"):
        seg_data = breakdown.get(seg) if isinstance(breakdown, dict) else None
        try:
            pct = int(float((seg_data or {}).get("percent_optimized", 0) or 0))
        except Exception:
            pct = 0
        out[seg] = max(0, min(100, pct))
    return out

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


def _confirm_cascade_delete_action(*, title: str, subtitle: str, template: str, action_name: str):
    """
    Small helper to implement an "extra confirmation" delete action for admin.
    """

    def _action(modeladmin, request, queryset):
        opts = modeladmin.model._meta

        if request.POST.get("post") == "yes" and request.POST.get("confirm_cascade_delete") == "yes":
            n = queryset.count()
            queryset.delete()
            modeladmin.message_user(
                request, _(f"Deleted {n} {opts.verbose_name_plural} and related data."), level=messages.SUCCESS
            )
            return None

        deletable_objects, model_count, perms_needed, protected = get_deleted_objects(
            queryset, request, modeladmin.admin_site
        )
        context = {
            **modeladmin.admin_site.each_context(request),
            "title": title,
            "subtitle": subtitle,
            "objects_name": str(opts.verbose_name_plural),
            "deletable_objects": deletable_objects,
            "model_count": dict(model_count).items(),
            "queryset": queryset,
            "perms_needed": perms_needed,
            "protected": protected,
            "opts": opts,
            "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            "action_name": action_name,
            "media": modeladmin.media,
        }
        return TemplateResponse(request, template, context)

    return _action


@admin.register(WorkoutSession)
class WorkoutSessionAdmin(admin.ModelAdmin):
    list_display  = ("user", "date")
    list_filter   = ("user", "date")  #  correct way
    inlines       = [WorkoutEntryInline]
    actions = ["safe_delete_workout_sessions"]

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    @admin.action(description="Delete selected workout sessions (extra confirmation)")
    def safe_delete_workout_sessions(self, request, queryset):
        return _confirm_cascade_delete_action(
            title=_("Confirm workout session deletion (cascade)"),
            subtitle=_("This will permanently delete the selected session(s) and related workout entries."),
            template="admin/workouts/confirm_cascade_delete.html",
            action_name="safe_delete_workout_sessions",
        )(self, request, queryset)

    def get_routine_type(self, obj):
        return obj.user_routine.routine_type if obj.user_routine else None
    get_routine_type.short_description = "Routine Type"


@admin.register(UserRoutine)
class UserRoutineAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "routine_type", "is_active", "created_at")
    list_filter = ("routine_type", "is_active", "created_at")
    search_fields = ("user__email", "user__username", "id")
    actions = [
        "regenerate_user_routines",
        "populate_scan_and_optimization",
        "regenerate_and_populate",
        "safe_delete_user_routines",
    ]

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    @admin.action(description="Delete selected user routines (extra confirmation)")
    def safe_delete_user_routines(self, request, queryset):
        return _confirm_cascade_delete_action(
            title=_("Confirm routine deletion (cascade)"),
            subtitle=_("This will permanently delete the selected routine(s) and related sessions/entries."),
            template="admin/workouts/confirm_cascade_delete.html",
            action_name="safe_delete_user_routines",
        )(self, request, queryset)

    @admin.action(description="Regenerate routines for selected routine's user(s)")
    def regenerate_user_routines(self, request, queryset):
        user_ids = list(queryset.values_list("user_id", flat=True).distinct())
        ok = 0
        failed = 0
        for uid in user_ids:
            try:
                routine = queryset.filter(user_id=uid).order_by("-created_at").first()
                user = routine.user if routine else None
                if not user:
                    continue
                latest_report = PostureReport.objects.filter(user=user).order_by("-created_at").first()
                breakdown = None
                if latest_report and isinstance(latest_report.data, dict):
                    breakdown = latest_report.data.get("optimization_breakdown")
                if not breakdown:
                    breakdown = _default_breakdown()
                generate_user_routines(user, breakdown)
                ok += 1
            except Exception as e:
                failed += 1
                self.message_user(request, f"Failed to regenerate routines for user_id={uid}: {e}", level=messages.ERROR)

        if ok:
            self.message_user(request, f"Regenerated routines for {ok} user(s).", level=messages.SUCCESS)
        if failed and not ok:
            self.message_user(request, f"Failed for {failed} user(s).", level=messages.ERROR)

    @admin.action(description="Populate scan_score + optimization_breakdown (latest scan or demo defaults)")
    def populate_scan_and_optimization(self, request, queryset):
        ok = 0
        failed = 0
        for routine in queryset.select_related("user"):
            try:
                latest_report = PostureReport.objects.filter(user=routine.user).order_by("-created_at").first()
                data = latest_report.data if (latest_report and isinstance(latest_report.data, dict)) else {}
                breakdown = data.get("optimization_breakdown") if isinstance(data, dict) else None
                if not breakdown:
                    breakdown = _default_breakdown()
                scan_score = data.get("scan_score") if isinstance(data, dict) else None
                if not isinstance(scan_score, dict) or not scan_score:
                    scan_score = _demo_scan_score_from_breakdown(breakdown)

                routine.optimization_breakdown = breakdown
                routine.scan_score = scan_score
                routine.save(update_fields=["optimization_breakdown", "scan_score", "updated_at"])
                ok += 1
            except Exception as e:
                failed += 1
                self.message_user(
                    request,
                    f"Failed to populate scores for routine_id={routine.id}: {e}",
                    level=messages.ERROR,
                )

        if ok:
            self.message_user(request, f"Populated scores for {ok} routine(s).", level=messages.SUCCESS)
        if failed and not ok:
            self.message_user(request, f"Failed for {failed} routine(s).", level=messages.ERROR)

    @admin.action(description="Regenerate routines + populate scan/optimization (one click)")
    def regenerate_and_populate(self, request, queryset):
        """
        One-click admin tool:
        - Regenerate routines for the selected routines' users (deactivate old, create new)
        - Populate scan_score + optimization_breakdown on the new active routines
        """
        user_ids = list(queryset.values_list("user_id", flat=True).distinct())
        ok = 0
        failed = 0
        for uid in user_ids:
            try:
                routine = queryset.filter(user_id=uid).order_by("-created_at").first()
                user = routine.user if routine else None
                if not user:
                    continue

                latest_report = PostureReport.objects.filter(user=user).order_by("-created_at").first()
                data = latest_report.data if (latest_report and isinstance(latest_report.data, dict)) else {}
                breakdown = data.get("optimization_breakdown") if isinstance(data, dict) else None
                if not breakdown:
                    breakdown = _default_breakdown()

                # Step 1: regenerate (creates new active routines)
                generate_user_routines(user, breakdown)

                # Step 2: populate on the new active routines
                active_routines = UserRoutine.objects.filter(user=user, is_active=True)
                for r in active_routines:
                    scan_score = data.get("scan_score") if isinstance(data, dict) else None
                    if not isinstance(scan_score, dict) or not scan_score:
                        scan_score = _demo_scan_score_from_breakdown(breakdown)
                    r.optimization_breakdown = breakdown
                    r.scan_score = scan_score
                    r.save(update_fields=["optimization_breakdown", "scan_score", "updated_at"])

                ok += 1
            except Exception as e:
                failed += 1
                self.message_user(
                    request,
                    f"Failed regenerate+populate for user_id={uid}: {e}",
                    level=messages.ERROR,
                )

        if ok:
            self.message_user(request, f"Regenerated+populated for {ok} user(s).", level=messages.SUCCESS)
        if failed and not ok:
            self.message_user(request, f"Failed for {failed} user(s).", level=messages.ERROR)