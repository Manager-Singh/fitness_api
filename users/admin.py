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

from .models import DailyLog, FriendInvite, Friendship, HeightLedger, NotificationEventLog, OTP, PostureState, User
from django.apps import apps as django_apps


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


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    inlines = ()
    list_display = ("id", "email", "username", "account_tier", "is_active", "is_staff", "date_joined")
    search_fields = ("email", "username")
    list_filter = ("account_tier", "is_active", "is_staff")
    actions = ["regenerate_routines", "delete_selected_users_with_confirm"]

    # Add the "profile" + "posture questions" one-to-one records inline on the user.
    class UserProfileInline(admin.StackedInline):
        model = UserProfile
        can_delete = False
        extra = 0

    class PostureQuestionInline(admin.StackedInline):
        model = PostureQuestion
        can_delete = False
        extra = 0

    inlines = (UserProfileInline, PostureQuestionInline)

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
                WorkoutEntry.objects.filter(session__user_id__in=user_ids).delete()
                WorkoutSession.objects.filter(user_id__in=user_ids).delete()

                # Nutrition/lifestyle logs.
                NutraEntry.objects.filter(session__user_id__in=user_ids).delete()
                NutraSession.objects.filter(user_id__in=user_ids).delete()

                # Routines: exercises first, then routines.
                routines = UserRoutine.objects.filter(user_id__in=user_ids)
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