from __future__ import annotations

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.admin.utils import get_deleted_objects
from django.db import transaction
from django.template.response import TemplateResponse
from django.utils.translation import gettext_lazy as _

from posture.models import PostureReport
from posture_questions.models import PostureQuestion
from nutration.models_log import NutraEntry, NutraSession
from user_profile.models import Payment, UserProfile
from utils.posture.height_constants import POSTURE_SEGMENT_MAX_LOSS_CM, posture_segment_opt_pct
from utils.routine_genrate import generate_user_routines
from workouts.models import WorkoutEntry, WorkoutSession, UserRoutine, UserRoutineExercise

from chatbot.models import ChatMessage
from height_analysis.models import GeneticHeightEstimate, HeightGrowthProjection
from posture_analysis.models import UserPosturalOptimizationData, PosturalRecommendation

from .admin_ui import (
    badge,
    badge_bool,
    badge_points,
    badge_tier,
    fmt_cm,
    progress_dashboard_html,
    um_to_cm,
)
from .models import DailyLog, FriendInvite, Friendship, HeightLedger, NotificationEventLog, OTP, PostureState, User
from .spec_runtime import compute_daily_height_for_user
from django.apps import apps as django_apps
from django.utils.html import format_html
from utils.user_time import user_today


def _maybe_delete_model(app_label: str, model_name: str, **filters):
    """
    Delete rows for a model only if its app is installed.
    This keeps admin safe across deployments where optional apps are not enabled.
    """
    if not django_apps.is_installed(app_label):
        return
    Model = django_apps.get_model(app_label, model_name)
    if Model is None:
        return
    Model.objects.filter(**filters).delete()


def _um_to_cm(um) -> str:
    try:
        return f"{int(um or 0) / 10000.0:.4f}"
    except (TypeError, ValueError):
        return "0"


class ScanCompletedFilter(admin.SimpleListFilter):
    title = "scan completed"
    parameter_name = "scan_done"

    def lookups(self, request, model_admin):
        return (("yes", "Yes"), ("no", "No"))

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(posture_state__scan_completed=True)
        if self.value() == "no":
            return queryset.exclude(posture_state__scan_completed=True)
        return queryset


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


class PostureStateInline(admin.StackedInline):
    model = PostureState
    can_delete = False
    extra = 0
    max_num = 1
    readonly_fields = (
        "scan_completed",
        "questionnaire_completed",
        "assessment_sources_used",
        "total_recoverable_cm",
        "segments_summary",
        "last_recalculated_at",
        "last_scan_at",
        "questionnaire_completed_at",
        "updated_at",
    )
    fields = readonly_fields
    verbose_name = "Posture"
    verbose_name_plural = "Posture optimization (live state)"

    @admin.display(description="Total recoverable")
    def total_recoverable_cm(self, obj):
        return f"{fmt_cm(obj.total_recoverable_loss_um)} cm"

    @admin.display(description="Segment losses")
    def segments_summary(self, obj):
        if not obj:
            return "—"
        from users.admin_ui import _segment_bars

        return _segment_bars(obj)


class DailyLogInline(admin.TabularInline):
    """Per-day point totals written by compute_daily_height_for_user (cron / pipeline)."""
    model = DailyLog
    fk_name = "user"
    extra = 0
    max_num = 0
    can_delete = False
    ordering = ("-log_date",)
    readonly_fields = (
        "day_marker",
        "engine1_points",
        "engine2_points",
        "exercise_points",
        "food_points",
        "lifestyle_points",
        "habit_points",
        "validated_badge",
        "genetic_average_cm",
        "updated_at",
    )
    fields = readonly_fields
    verbose_name = "Day"
    verbose_name_plural = "Daily progress — points per day (last 30)"

    def get_queryset(self, request):
        return super().get_queryset(request)[:30]

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Date")
    def day_marker(self, obj):
        is_today = obj.log_date == user_today(obj.user)
        if is_today:
            return format_html(
                '<span class="hm-row-today-label">{}</span> {}',
                obj.log_date,
                badge("TODAY", color="#166534", bg="#dcfce7"),
            )
        return obj.log_date

    @admin.display(description="OK")
    def validated_badge(self, obj):
        return badge_bool(obj.validated)


class HeightLedgerInline(admin.TabularInline):
    """Height ledger entries — daily_compute rows are the canonical height chain."""
    model = HeightLedger
    fk_name = "user"
    extra = 0
    max_num = 0
    can_delete = False
    ordering = ("-log_date", "-created_at")
    readonly_fields = (
        "day_marker",
        "delta_cm_display",
        "cumulative_cm_display",
        "engine1_delta_cm",
        "engine2_delta_cm",
        "bio_delta_cm",
    )
    fields = readonly_fields
    verbose_name = "Day"
    verbose_name_plural = "Height ledger — daily_compute (last 30)"

    def get_queryset(self, request):
        return super().get_queryset(request).filter(entry_type="daily_compute")[:30]

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="Date")
    def day_marker(self, obj):
        is_today = obj.log_date == user_today(obj.user)
        if is_today:
            return format_html(
                '{} {}',
                obj.log_date,
                badge("TODAY", color="#166534", bg="#dcfce7"),
            )
        return obj.log_date

    @admin.display(description="Δ height")
    def delta_cm_display(self, obj):
        val = fmt_cm(obj.delta_um)
        if um_to_cm(obj.delta_um) > 0:
            return format_html('<strong style="color:#0f766e">+{} cm</strong>', val)
        return f"{val} cm"

    @admin.display(description="Cumulative")
    def cumulative_cm_display(self, obj):
        return format_html("<strong>{} cm</strong>", fmt_cm(obj.cumulative_um))

    @admin.display(description="E1 Δ")
    def engine1_delta_cm(self, obj):
        return f"{fmt_cm(obj.engine1_delta_um)} cm"

    @admin.display(description="E2 Δ")
    def engine2_delta_cm(self, obj):
        from users.spec_runtime import _um_from_dm

        return f"{fmt_cm(_um_from_dm(obj.engine2_delta_dm))} cm"

    @admin.display(description="Bio Δ")
    def bio_delta_cm(self, obj):
        return f"{fmt_cm(obj.bio_delta_um)} cm"


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "email",
        "tier_badge",
        "cumulative_height_display",
        "today_engines_display",
        "pipeline_status",
        "is_active",
        "date_joined",
    )
    list_display_links = ("id", "email")
    search_fields = ("email", "username", "id")
    list_filter = ("account_tier", "is_active", "is_staff", ScanCompletedFilter)
    list_per_page = 25
    actions = [
        "recompute_today_progress",
        "regenerate_routines",
        "delete_selected_users_with_confirm",
    ]
    readonly_fields = ("progress_summary",)

    class Media:
        css = {"all": ("admin/css/user_progress.css",)}

    change_form_template = "admin/users/change_form.html"

    class UserProfileInline(admin.StackedInline):
        model = UserProfile
        can_delete = False
        extra = 0
        classes = ("collapse",)
        verbose_name_plural = "Profile (collapsed)"

    class PostureQuestionInline(admin.StackedInline):
        model = PostureQuestion
        can_delete = False
        extra = 0
        classes = ("collapse",)
        verbose_name_plural = "Questionnaire answers (collapsed)"

    inlines = (
        PostureStateInline,
        DailyLogInline,
        HeightLedgerInline,
        UserProfileInline,
        PostureQuestionInline,
    )

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return (
                (
                    None,
                    {
                        "fields": (
                            "email",
                            "username",
                            "account_tier",
                            "is_active",
                            "is_staff",
                        ),
                    },
                ),
            )
        return (
            (
                "Progress dashboard",
                {
                    "fields": ("progress_summary",),
                    "classes": ("wide", "hm-progress-fieldset"),
                    "description": "Live snapshot from DailyLog + HeightLedger. Updated by cron every 5 minutes.",
                },
            ),
            (
                "Account",
                {
                    "fields": (
                        "email",
                        "username",
                        "account_tier",
                        "timezone",
                        "last_reset_date",
                        "is_active",
                        "is_staff",
                        "trial_start",
                        "trial_end",
                        "date_joined",
                    ),
                    "classes": ("collapse",),
                },
            ),
        )

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return (
                "progress_summary",
                "last_reset_date",
                "date_joined",
            )
        return ()

    @admin.display(description="Tier", ordering="account_tier")
    def tier_badge(self, obj):
        return badge_tier(obj.account_tier)

    @admin.display(description="Height")
    def cumulative_height_display(self, obj):
        row = (
            HeightLedger.objects.filter(user=obj, entry_type="daily_compute")
            .order_by("-log_date", "-created_at")
            .first()
        )
        if not row:
            return "—"
        return format_html("<strong>{} cm</strong>", fmt_cm(row.cumulative_um))

    @admin.display(description="Today E1 / E2")
    def today_engines_display(self, obj):
        daily = DailyLog.objects.filter(user=obj, log_date=user_today(obj)).first()
        if not daily:
            return "—"
        return format_html(
            "{} / {}",
            badge_points(daily.engine1_points, highlight=True),
            badge_points(daily.engine2_points),
        )

    @admin.display(description="Pipeline")
    def pipeline_status(self, obj):
        today = user_today(obj)
        if obj.last_reset_date == today:
            return badge("OK", color="#166534", bg="#dcfce7")
        if obj.last_reset_date:
            return badge(str(obj.last_reset_date), color="#b45309", bg="#fef3c7")
        return badge("Never", color="#64748b", bg="#f1f5f9")

    @admin.display(description="Progress dashboard")
    def progress_summary(self, obj):
        return progress_dashboard_html(obj)

    @admin.action(description="Recompute today's progress (force)")
    def recompute_today_progress(self, request, queryset):
        n = 0
        for user in queryset:
            compute_daily_height_for_user(user, log_date=user_today(user), force_recompute=True)
            n += 1
        self.message_user(
            request,
            f"Recomputed progress for {n} user(s) (local today).",
            level=messages.SUCCESS,
        )

    def get_actions(self, request):
        actions = super().get_actions(request)
        # Remove the default bulk delete; we provide a safer confirmation flow.
        actions.pop("delete_selected", None)
        return actions

    @admin.action(description="Regenerate routines (POSTURE/HGH) for selected users")
    def regenerate_routines(self, request, queryset):
        ok = 0
        failed = 0
        for user in queryset:
            try:
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
                self.message_user(
                    request,
                    f"Failed to regenerate routines for user_id={user.id}: {e}",
                    level=messages.ERROR,
                )

        if ok:
            self.message_user(request, f"Regenerated routines for {ok} user(s).", level=messages.SUCCESS)
        if failed and not ok:
            self.message_user(request, f"Failed for {failed} user(s).", level=messages.ERROR)

    @admin.action(description="Delete selected users (extra confirmation; deletes related data)")
    def delete_selected_users_with_confirm(self, request, queryset):
        """
        Safer bulk-delete for users.

        Django already has a confirmation page for deletes, but this adds an extra
        explicit checkbox acknowledgement because deleting a user cascades to many
        related records (workouts, nutrition, posture, ledgers, etc.).
        """
        opts = self.model._meta
        using = None

        # Step 2: perform delete only after explicit acknowledgement.
        if request.POST.get("post") == "yes" and request.POST.get("confirm_cascade_delete") == "yes":
            # IMPORTANT:
            # We cannot rely on `queryset.delete()` because some relations are PROTECT
            # (e.g. WorkoutSession.user_routine). Delete in the correct order:
            # sessions/entries -> routines -> user, plus other user-linked rows.
            users = list(queryset)
            user_ids = [u.id for u in users]

            with transaction.atomic():
                # Auth/runtime related rows first.
                OTP.objects.filter(user_id__in=user_ids).delete()
                NotificationEventLog.objects.filter(user_id__in=user_ids).delete()

                # Social graph.
                Friendship.objects.filter(user_id_a_id__in=user_ids).delete()
                Friendship.objects.filter(user_id_b_id__in=user_ids).delete()
                FriendInvite.objects.filter(inviter_id__in=user_ids).delete()
                FriendInvite.objects.filter(accepted_by_id__in=user_ids).delete()

                # Chat history.
                ChatMessage.objects.filter(user_id__in=user_ids).delete()

                # Leaderboard / history ledgers (points + height).
                DailyLog.objects.filter(user_id__in=user_ids).delete()
                HeightLedger.objects.filter(user_id__in=user_ids).delete()
                PostureState.objects.filter(user_id__in=user_ids).delete()

                # Workouts: delete entries then sessions (sessions reference routines via PROTECT).
                # NOTE: some legacy rows have WorkoutSession.user = NULL but still reference a routine.
                # Delete by BOTH dimensions to ensure PROTECT does not block routine deletes.
                routines = UserRoutine.objects.filter(user_id__in=user_ids)
                routine_ids = list(routines.values_list("id", flat=True))

                WorkoutEntry.objects.filter(session__user_id__in=user_ids).delete()
                if routine_ids:
                    WorkoutEntry.objects.filter(session__user_routine_id__in=routine_ids).delete()

                WorkoutSession.objects.filter(user_id__in=user_ids).delete()
                if routine_ids:
                    WorkoutSession.objects.filter(user_routine_id__in=routine_ids).delete()

                # Nutrition/lifestyle logs.
                NutraEntry.objects.filter(session__user_id__in=user_ids).delete()
                NutraSession.objects.filter(user_id__in=user_ids).delete()

                # Routines: exercises first, then routines.
                UserRoutineExercise.objects.filter(routine__in=routines).delete()
                routines.delete()

                # Posture reports (scan history).
                PostureReport.objects.filter(user_id__in=user_ids).delete()

                # Height analysis / projections.
                HeightGrowthProjection.objects.filter(genetic_estimate__user_id__in=user_ids).delete()
                GeneticHeightEstimate.objects.filter(user_id__in=user_ids).delete()

                # AI posture analysis.
                PosturalRecommendation.objects.filter(user_data__user_id__in=user_ids).delete()
                UserPosturalOptimizationData.objects.filter(user_id__in=user_ids).delete()

                # Legacy submissions.
                # Some deployments don't include these optional apps.
                _maybe_delete_model("wellness_tracker", "WellnessSubmission", user_id__in=user_ids)
                _maybe_delete_model("exercise", "ExerciseSubmission", user_id__in=user_ids)

                # Payments stored under user_profile app.
                Payment.objects.filter(user_id__in=user_ids).delete()

                # Finally delete the users (cascades to one-to-ones like profile/posture_questions).
                n = len(users)
                queryset.delete()

            self.message_user(
                request,
                _(f"Deleted {n} user(s) and related data (workouts, nutrition, routines, posture reports)."),
                level=messages.SUCCESS,
            )
            return None

        # Step 1: show confirmation page
        deletable_objects, model_count, perms_needed, protected = get_deleted_objects(
            queryset, request, self.admin_site
        )
        context = {
            **self.admin_site.each_context(request),
            "title": _("Confirm user deletion (cascade)"),
            "subtitle": _("This will permanently delete the selected user(s) and ALL related data."),
            "objects_name": str(opts.verbose_name_plural),
            "deletable_objects": deletable_objects,
            "model_count": dict(model_count).items(),
            "queryset": queryset,
            "perms_needed": perms_needed,
            "protected": protected,
            "opts": opts,
            "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            "media": self.media,
        }
        return TemplateResponse(request, "admin/users/confirm_cascade_delete.html", context)


@admin.register(DailyLog)
class DailyLogAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "log_date",
        "engine1_badge",
        "engine2_badge",
        "exercise_points",
        "food_points",
        "lifestyle_points",
        "habit_points",
        "validated_badge",
    )
    list_filter = ("log_date", "validated", "user__account_tier")
    search_fields = ("user__email", "user__username", "user__id")
    raw_id_fields = ("user",)
    ordering = ("-log_date",)
    date_hierarchy = "log_date"
    list_per_page = 50

    class Media:
        css = {"all": ("admin/css/user_progress.css",)}

    @admin.display(description="E1", ordering="engine1_points")
    def engine1_badge(self, obj):
        return badge_points(obj.engine1_points, highlight=True)

    @admin.display(description="E2", ordering="engine2_points")
    def engine2_badge(self, obj):
        return badge_points(obj.engine2_points)

    @admin.display(description="Validated", ordering="validated")
    def validated_badge(self, obj):
        return badge_bool(obj.validated)


@admin.register(HeightLedger)
class HeightLedgerAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "log_date",
        "entry_type",
        "delta_display",
        "cumulative_display",
        "engine1_delta_cm",
        "engine2_delta_cm",
    )
    list_filter = ("entry_type", "log_date")
    search_fields = ("user__email", "user__username", "user__id")
    raw_id_fields = ("user",)
    ordering = ("-log_date", "-created_at")
    date_hierarchy = "log_date"
    list_per_page = 50

    class Media:
        css = {"all": ("admin/css/user_progress.css",)}

    @admin.display(description="Δ height", ordering="delta_um")
    def delta_display(self, obj):
        val = fmt_cm(obj.delta_um)
        if um_to_cm(obj.delta_um) > 0:
            return format_html('<span style="color:#0f766e;font-weight:600">+{} cm</span>', val)
        return f"{val} cm"

    @admin.display(description="Cumulative", ordering="cumulative_um")
    def cumulative_display(self, obj):
        return format_html("<strong>{} cm</strong>", fmt_cm(obj.cumulative_um))

    @admin.display(description="E1 Δ")
    def engine1_delta_cm(self, obj):
        return f"{fmt_cm(obj.engine1_delta_um)} cm"

    @admin.display(description="E2 Δ")
    def engine2_delta_cm(self, obj):
        from users.spec_runtime import _um_from_dm

        return f"{fmt_cm(_um_from_dm(obj.engine2_delta_dm))} cm"


@admin.register(PostureState)
class PostureStateAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "scan_badge",
        "questionnaire_badge",
        "assessment_sources_used",
        "total_recoverable_cm",
        "last_recalculated_at",
    )
    list_filter = ("scan_completed", "questionnaire_completed", "assessment_sources_used")
    search_fields = ("user__email", "user__username", "user__id")
    raw_id_fields = ("user",)
    list_per_page = 50

    @admin.display(description="Scan", ordering="scan_completed")
    def scan_badge(self, obj):
        return badge_bool(obj.scan_completed)

    @admin.display(description="Questionnaire", ordering="questionnaire_completed")
    def questionnaire_badge(self, obj):
        return badge_bool(obj.questionnaire_completed)

    @admin.display(description="Recoverable")
    def total_recoverable_cm(self, obj):
        return f"{fmt_cm(obj.total_recoverable_loss_um)} cm"