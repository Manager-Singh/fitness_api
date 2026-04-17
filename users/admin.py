from __future__ import annotations

from django.contrib import admin, messages

from posture.models import PostureReport
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
    list_display = ("id", "email", "username", "account_tier", "is_active", "is_staff", "date_joined")
    search_fields = ("email", "username")
    list_filter = ("account_tier", "is_active", "is_staff")
    actions = ["regenerate_routines"]

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