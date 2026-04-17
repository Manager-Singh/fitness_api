from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date as date_type, datetime, timedelta
from typing import Any

from django import forms
from django.contrib import admin, messages
from django.contrib.admin import widgets as admin_widgets
from django.urls import reverse
from django.utils.html import format_html
from django.db import transaction
from django.db import models
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import path
from django.utils import timezone

from apibackend.test_seed_views import (
    _ensure_min_exercise_fixtures,
    _ensure_min_nutrition_fixtures,
    _seed_day_logs,
    _seed_scan,
)
from seed_tools.models import UserDataSeedRun
from user_profile.models import UserProfile
from users.models import User
from users.spec_runtime import rebuild_ledger_from_date
from workouts.models import WorkoutEntry, WorkoutSession
from nutration.models_log import NutraEntry, NutraSession
from posture.models import PostureReport


@dataclass
class SeedDayLog:
    date: str
    deleted: dict[str, int]
    created: dict[str, int]


class UserDataSeedRunForm(forms.ModelForm):
    date = forms.DateField(required=True, help_text="Seed target day (UTC).")
    days = forms.IntegerField(required=False, min_value=0, initial=0, help_text="Also seed N previous days.")
    variant = forms.ChoiceField(
        required=False,
        choices=(("", "Auto (from profile age)"), ("teen", "Teen"), ("adult", "Adult")),
        initial="",
    )
    include_scan = forms.BooleanField(required=False, initial=True)

    class Meta:
        model = UserDataSeedRun
        fields = ("target_user",)


class SeedToolForm(forms.Form):
    class Action(models.TextChoices):
        SEED = "seed", "Seed dummy data"
        DELETE = "delete", "Delete dummy data"

    action = forms.ChoiceField(choices=Action.choices, initial=Action.SEED)
    target_user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=admin_widgets.ForeignKeyRawIdWidget(UserDataSeedRun._meta.get_field("target_user").remote_field, admin.site),
    )
    date = forms.DateField(required=True, help_text="Target day (UTC).")
    days = forms.IntegerField(required=False, min_value=0, initial=0, help_text="Also include N previous days.")
    variant = forms.ChoiceField(
        required=False,
        choices=(("", "Auto (from profile age)"), ("teen", "Teen"), ("adult", "Adult")),
        initial="",
    )
    include_scan = forms.BooleanField(required=False, initial=True)


@admin.register(UserDataSeedRun)
class UserDataSeedRunAdmin(admin.ModelAdmin):
    form = UserDataSeedRunForm
    list_display = ("id", "created_at", "created_by", "target_user", "status", "view_seeded_data")
    list_filter = ("status", "created_at")
    search_fields = ("target_user__email", "created_by__email")
    readonly_fields = ("created_at", "created_by", "params", "status", "result")
    raw_id_fields = ("target_user",)  # searchable popup

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("tool/", self.admin_site.admin_view(self.seed_tool_view), name="seed_tools_tool"),
            path("<int:run_id>/summary/", self.admin_site.admin_view(self.seed_run_summary_view), name="seed_tools_run_summary"),
            path("<int:run_id>/delete-data/", self.admin_site.admin_view(self.delete_data_for_run_view), name="seed_tools_run_delete_data"),
        ]
        return custom + urls

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ("created_at", "created_by", "params", "status", "result")
        return super().get_readonly_fields(request, obj=obj)

    def get_fields(self, request, obj=None):
        # On the Add form we must show the extra form fields that drive seeding.
        if obj is None:
            return ("target_user", "date", "days", "variant", "include_scan")
        # Existing runs are logs; show only the persisted fields.
        return ("target_user", "created_at", "created_by", "params", "status", "result")

    def has_change_permission(self, request, obj=None):
        # Seed runs are append-only logs; allow viewing but not editing.
        if obj is not None and request.method not in {"GET", "HEAD", "OPTIONS"}:
            return False
        return super().has_change_permission(request, obj=obj)

    @admin.display(description="Seeded data", ordering="id")
    def view_seeded_data(self, obj: UserDataSeedRun):
        url = reverse("admin:seed_tools_run_summary", args=[obj.pk])
        return format_html('<a class="button" href="{}">View</a>', url)

    def seed_run_summary_view(self, request: HttpRequest, run_id: int) -> HttpResponse:
        run = UserDataSeedRun.objects.filter(pk=run_id).select_related("target_user", "created_by").first()
        if not run:
            messages.error(request, "Seed run not found.")
            return redirect("../")

        result = run.result or {}
        params = run.params or {}

        # Table names (actual DB tables) for clarity
        tables = {
            "UserProfile": UserProfile._meta.db_table,
            "PostureReport": PostureReport._meta.db_table,
            "WorkoutSession": WorkoutSession._meta.db_table,
            "WorkoutEntry": WorkoutEntry._meta.db_table,
            "NutraSession": NutraSession._meta.db_table,
            "NutraEntry": NutraEntry._meta.db_table,
        }

        context = {
            **self.admin_site.each_context(request),
            "title": f"Seed run summary #{run.pk}",
            "run": run,
            "params": params,
            "result": result,
            "tables": tables,
            "days": result.get("days") or [],
            "delete_url": reverse("admin:seed_tools_run_delete_data", args=[run.pk]),
        }
        return render(request, "admin/seed_tools/run_summary.html", context)

    def delete_data_for_run_view(self, request: HttpRequest, run_id: int) -> HttpResponse:
        if request.method != "POST":
            return redirect(reverse("admin:seed_tools_run_summary", args=[run_id]))

        run = UserDataSeedRun.objects.filter(pk=run_id).select_related("target_user", "created_by").first()
        if not run:
            messages.error(request, "Seed run not found.")
            return redirect("../")

        params = run.params or {}
        target_user: User = run.target_user
        include_scan = bool(params.get("include_scan", True))

        # Parse date range from stored params (seed runs store YYYY-MM-DD).
        try:
            on_date = datetime.strptime(str(params.get("date")), "%Y-%m-%d").date()
        except Exception:
            messages.error(request, "Run params missing/invalid date; cannot delete.")
            return redirect(reverse("admin:seed_tools_run_summary", args=[run_id]))

        try:
            days = int(params.get("days") or 0)
        except Exception:
            days = 0
        start_date = on_date - timedelta(days=max(0, days))

        delete_run = UserDataSeedRun(
            created_by=request.user if request.user.is_authenticated else None,
            target_user=target_user,
            params={
                "action": "delete",
                "source_run_id": run.pk,
                "date": str(on_date),
                "days": days,
                "include_scan": include_scan,
            },
        )

        try:
            with transaction.atomic():
                deleted_scan = 0
                if include_scan:
                    qs = PostureReport.objects.filter(user=target_user, raw_request_data__seeded=True)
                    deleted_scan = qs.count()
                    qs.delete()

                day_logs: list[SeedDayLog] = []
                d = start_date
                while d <= on_date:
                    dw_e = WorkoutEntry.objects.filter(session__user=target_user, session__date=d).count()
                    dw_s = WorkoutSession.objects.filter(user=target_user, date=d).count()
                    dn_e = NutraEntry.objects.filter(session__user=target_user, session__date=d).count()
                    dn_s = NutraSession.objects.filter(user=target_user, date=d).count()

                    WorkoutEntry.objects.filter(session__user=target_user, session__date=d).delete()
                    WorkoutSession.objects.filter(user=target_user, date=d).delete()
                    NutraEntry.objects.filter(session__user=target_user, session__date=d).delete()
                    NutraSession.objects.filter(user=target_user, date=d).delete()

                    day_logs.append(
                        SeedDayLog(
                            date=str(d),
                            deleted={"WorkoutEntry": dw_e, "WorkoutSession": dw_s, "NutraEntry": dn_e, "NutraSession": dn_s},
                            created={},
                        )
                    )
                    d += timedelta(days=1)

            delete_run.status = UserDataSeedRun.Status.SUCCESS
            delete_run.result = {
                "ok": True,
                "action": "delete",
                "deleted_from": str(start_date),
                "deleted_to": str(on_date),
                "include_scan": include_scan,
                "deleted_scan_reports": deleted_scan,
                "days": [asdict(x) for x in day_logs],
                "timestamp_utc": timezone.now().isoformat(),
            }
            delete_run.save()
            messages.success(request, f"Deleted data for user={target_user.id} from {start_date} to {on_date}.")
        except Exception as e:
            delete_run.status = UserDataSeedRun.Status.FAILED
            delete_run.result = {"ok": False, "action": "delete", "error": str(e), "timestamp_utc": timezone.now().isoformat()}
            delete_run.save()
            messages.error(request, f"Delete failed: {e}")

        return redirect(reverse("admin:seed_tools_run_summary", args=[run_id]))

    def seed_tool_view(self, request: HttpRequest) -> HttpResponse:
        """
        Direct admin tool:
          - pick user (searchable)
          - choose date + previous days
          - seed OR delete dummy data
          - always records an immutable run log
        """
        if request.method == "POST":
            form = SeedToolForm(request.POST)
            if form.is_valid():
                action = form.cleaned_data["action"]
                target_user: User = form.cleaned_data["target_user"]
                on_date: date_type = form.cleaned_data["date"]
                days: int = int(form.cleaned_data.get("days") or 0)
                include_scan: bool = bool(form.cleaned_data.get("include_scan", True))
                variant: str = (form.cleaned_data.get("variant") or "").strip().lower()

                profile = UserProfile.objects.filter(user=target_user).first()
                if not variant:
                    try:
                        age = int(float(getattr(profile, "age", 0) or 0))
                    except Exception:
                        age = 0
                    variant = "adult" if age >= 21 else "teen"
                if variant not in {"adult", "teen"}:
                    messages.error(request, "Variant must be teen or adult.")
                    return render(request, "admin/seed_tools/tool.html", {"form": form, "title": "User Data Seed Tool"})

                start_date = on_date - timedelta(days=max(0, days))

                run = UserDataSeedRun(
                    created_by=request.user if request.user.is_authenticated else None,
                    target_user=target_user,
                    params={
                        "action": action,
                        "date": str(on_date),
                        "days": days,
                        "variant": variant,
                        "include_scan": include_scan,
                    },
                )

                try:
                    with transaction.atomic():
                        if action == SeedToolForm.Action.DELETE:
                            # Delete only the date-range logs; this will remove any data in that range.
                            # This is intended for test environments / seeded accounts.
                            deleted_scan = 0
                            if include_scan:
                                qs = PostureReport.objects.filter(user=target_user, raw_request_data__seeded=True)
                                before = qs.count()
                                qs.delete()
                                deleted_scan = before

                            day_logs: list[SeedDayLog] = []
                            d = start_date
                            while d <= on_date:
                                dw_e = WorkoutEntry.objects.filter(session__user=target_user, session__date=d).count()
                                dw_s = WorkoutSession.objects.filter(user=target_user, date=d).count()
                                dn_e = NutraEntry.objects.filter(session__user=target_user, session__date=d).count()
                                dn_s = NutraSession.objects.filter(user=target_user, date=d).count()

                                WorkoutEntry.objects.filter(session__user=target_user, session__date=d).delete()
                                WorkoutSession.objects.filter(user=target_user, date=d).delete()
                                NutraEntry.objects.filter(session__user=target_user, session__date=d).delete()
                                NutraSession.objects.filter(user=target_user, date=d).delete()

                                day_logs.append(
                                    SeedDayLog(
                                        date=str(d),
                                        deleted={"WorkoutEntry": dw_e, "WorkoutSession": dw_s, "NutraEntry": dn_e, "NutraSession": dn_s},
                                        created={},
                                    )
                                )
                                d += timedelta(days=1)

                            run.status = UserDataSeedRun.Status.SUCCESS
                            run.result = {
                                "ok": True,
                                "action": "delete",
                                "deleted_scan_reports": deleted_scan,
                                "deleted_from": str(start_date),
                                "deleted_to": str(on_date),
                                "days": [asdict(x) for x in day_logs],
                                "timestamp_utc": timezone.now().isoformat(),
                            }
                            run.save()
                            messages.success(request, f"Deleted data for user={target_user.id} from {start_date} to {on_date}.")
                        else:
                            # Seed
                            fixtures = {
                                "nutrition": _ensure_min_nutrition_fixtures(),
                                "exercises": _ensure_min_exercise_fixtures(),
                            }

                            scan_created = 0
                            if include_scan:
                                before = PostureReport.objects.filter(user=target_user).count()
                                _seed_scan(target_user, on_date)
                                after = PostureReport.objects.filter(user=target_user).count()
                                scan_created = max(0, after - before)

                            day_logs: list[SeedDayLog] = []
                            d = start_date
                            while d <= on_date:
                                deleted_workout_entries = WorkoutEntry.objects.filter(session__user=target_user, session__date=d).count()
                                deleted_workout_sessions = WorkoutSession.objects.filter(user=target_user, date=d).count()
                                deleted_nutra_entries = NutraEntry.objects.filter(session__user=target_user, session__date=d).count()
                                deleted_nutra_sessions = NutraSession.objects.filter(user=target_user, date=d).count()

                                _seed_day_logs(target_user, d, variant, fixtures)

                                created_workout_entries = WorkoutEntry.objects.filter(session__user=target_user, session__date=d).count()
                                created_workout_sessions = WorkoutSession.objects.filter(user=target_user, date=d).count()
                                created_nutra_entries = NutraEntry.objects.filter(session__user=target_user, session__date=d).count()
                                created_nutra_sessions = NutraSession.objects.filter(user=target_user, date=d).count()

                                day_logs.append(
                                    SeedDayLog(
                                        date=str(d),
                                        deleted={
                                            "WorkoutEntry": deleted_workout_entries,
                                            "WorkoutSession": deleted_workout_sessions,
                                            "NutraEntry": deleted_nutra_entries,
                                            "NutraSession": deleted_nutra_sessions,
                                        },
                                        created={
                                            "WorkoutEntry": created_workout_entries,
                                            "WorkoutSession": created_workout_sessions,
                                            "NutraEntry": created_nutra_entries,
                                            "NutraSession": created_nutra_sessions,
                                        },
                                    )
                                )
                                d += timedelta(days=1)

                            rebuild_ledger_from_date(target_user, start_date)

                            run.status = UserDataSeedRun.Status.SUCCESS
                            run.result = {
                                "ok": True,
                                "action": "seed",
                                "seeded_from": str(start_date),
                                "seeded_to": str(on_date),
                                "variant": variant,
                                "include_scan": include_scan,
                                "scan_created": scan_created,
                                "days": [asdict(x) for x in day_logs],
                                "generated_recipe": {
                                    "workout": ["Wall Angels"] + (["HGH Sprint"] if variant == "teen" else []),
                                    "nutrition": ["Disc Lubrication: Salmon", "Posture Muscle Repair: Collagen"],
                                    "lifestyle_if_teen": ["Sleep", "Sunlight", "Meditation", "Hydration"],
                                },
                                "timestamp_utc": timezone.now().isoformat(),
                            }
                            run.save()
                            messages.success(request, f"Seeded data for user={target_user.id} from {start_date} to {on_date}.")

                except Exception as e:
                    run.status = UserDataSeedRun.Status.FAILED
                    run.result = {"ok": False, "error": str(e), "timestamp_utc": timezone.now().isoformat()}
                    run.save()
                    messages.error(request, f"Operation failed: {e}")

                return redirect("..")
        else:
            form = SeedToolForm(initial={"action": SeedToolForm.Action.SEED, "days": 0, "include_scan": True})

        return render(request, "admin/seed_tools/tool.html", {"form": form, "title": "User Data Seed Tool"})

    def save_model(self, request, obj: UserDataSeedRun, form, change):
        if change:
            return super().save_model(request, obj, form, change)

        target_user: User = form.cleaned_data["target_user"]
        on_date: date_type = form.cleaned_data["date"]
        days: int = int(form.cleaned_data.get("days") or 0)
        include_scan: bool = bool(form.cleaned_data.get("include_scan", True))
        variant: str = (form.cleaned_data.get("variant") or "").strip().lower()

        profile = UserProfile.objects.filter(user=target_user).first()
        if not variant:
            try:
                age = int(float(getattr(profile, "age", 0) or 0))
            except Exception:
                age = 0
            variant = "adult" if age >= 21 else "teen"
        if variant not in {"adult", "teen"}:
            messages.error(request, "Variant must be teen or adult.")
            return

        obj.created_by = request.user if request.user.is_authenticated else None
        obj.target_user = target_user
        obj.params = {
            "date": str(on_date),
            "days": days,
            "variant": variant,
            "include_scan": include_scan,
        }

        start_date = on_date - timedelta(days=max(0, days))
        fixtures = {
            "nutrition": _ensure_min_nutrition_fixtures(),
            "exercises": _ensure_min_exercise_fixtures(),
        }

        day_logs: list[SeedDayLog] = []
        scan_created = 0

        try:
            with transaction.atomic():
                # Scan seed
                if include_scan:
                    before = PostureReport.objects.filter(user=target_user).count()
                    _seed_scan(target_user, on_date)
                    after = PostureReport.objects.filter(user=target_user).count()
                    scan_created = max(0, after - before)

                # Per-day seed with explicit counts (pre + post)
                d = start_date
                while d <= on_date:
                    deleted_workout_entries = WorkoutEntry.objects.filter(session__user=target_user, session__date=d).count()
                    deleted_workout_sessions = WorkoutSession.objects.filter(user=target_user, date=d).count()
                    deleted_nutra_entries = NutraEntry.objects.filter(session__user=target_user, session__date=d).count()
                    deleted_nutra_sessions = NutraSession.objects.filter(user=target_user, date=d).count()

                    _seed_day_logs(target_user, d, variant, fixtures)

                    created_workout_entries = WorkoutEntry.objects.filter(session__user=target_user, session__date=d).count()
                    created_workout_sessions = WorkoutSession.objects.filter(user=target_user, date=d).count()
                    created_nutra_entries = NutraEntry.objects.filter(session__user=target_user, session__date=d).count()
                    created_nutra_sessions = NutraSession.objects.filter(user=target_user, date=d).count()

                    day_logs.append(
                        SeedDayLog(
                            date=str(d),
                            deleted={
                                "WorkoutEntry": deleted_workout_entries,
                                "WorkoutSession": deleted_workout_sessions,
                                "NutraEntry": deleted_nutra_entries,
                                "NutraSession": deleted_nutra_sessions,
                            },
                            created={
                                "WorkoutEntry": created_workout_entries,
                                "WorkoutSession": created_workout_sessions,
                                "NutraEntry": created_nutra_entries,
                                "NutraSession": created_nutra_sessions,
                            },
                        )
                    )
                    d += timedelta(days=1)

                # Ledger rebuild (part of "what seed affects")
                rebuild_ledger_from_date(target_user, start_date)

            obj.status = UserDataSeedRun.Status.SUCCESS
            obj.result = {
                "ok": True,
                "seeded_from": str(start_date),
                "seeded_to": str(on_date),
                "variant": variant,
                "include_scan": include_scan,
                "scan_created": scan_created,
                "days": [asdict(x) for x in day_logs],
                "timestamp_utc": timezone.now().isoformat(),
            }
            super().save_model(request, obj, form, change)
            messages.success(
                request,
                f"Seeded data for user={target_user.id} from {start_date} to {on_date} (variant={variant}).",
            )
        except Exception as e:
            obj.status = UserDataSeedRun.Status.FAILED
            obj.result = {
                "ok": False,
                "error": str(e),
                "seeded_from": str(start_date),
                "seeded_to": str(on_date),
                "variant": variant,
                "include_scan": include_scan,
                "timestamp_utc": timezone.now().isoformat(),
            }
            super().save_model(request, obj, form, change)
            messages.error(request, f"Seeding failed: {e}")

