from __future__ import annotations

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.admin.utils import get_deleted_objects
from django.template.response import TemplateResponse
from django.utils.translation import gettext_lazy as _

from posture.models import PostureReport
from posture_questions.models import PostureQuestion
from user_profile.models import UserProfile
from utils.posture.height_constants import POSTURE_SEGMENT_MAX_LOSS_CM, posture_segment_opt_pct
from utils.routine_genrate import generate_user_routines

from .models import User


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
            n = queryset.count()
            queryset.delete()
            self.message_user(request, _(f"Deleted {n} user(s) and related data."), level=messages.SUCCESS)
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