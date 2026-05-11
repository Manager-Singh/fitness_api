from datetime import date as dt, datetime, timedelta
from django.db.models import Q, Sum
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models_log import NutraSession, NutraEntry
from .serializers_log import (
    NutraEntryWriteSerializer, NutraEntryReadSerializer,
    NutraSessionSerializer
)
from utils.age import get_user_age
from utils.engine_routing import apply_engine_routing
from utils.check_payment import check_subscription_or_response
from workouts.models import WorkoutEntry
from users.models import DailyLog
from users.models import NotificationEventLog
from utils.user_time import user_localize_dt, user_today
from users.spec_runtime import rebuild_ledger_from_date
from utils.teen_nutrition_cap import (
    TEEN_CAP_EVENT_KEY,
    teen_cap_result,
)

class NutraLogViewSet(viewsets.ViewSet):
    @staticmethod
    def _resolve_log_date(request):
        now_utc = timezone.now()
        now_local = user_localize_dt(request.user, now_utc)
        log_date = now_local.date()
        grace_minutes = 5
        if now_local.hour == 0 and now_local.minute < grace_minutes:
            client_ts = request.data.get("client_timestamp")
            if client_ts:
                try:
                    parsed = datetime.fromisoformat(str(client_ts).replace("Z", "+00:00"))
                    if timezone.is_naive(parsed):
                        parsed = timezone.make_aware(parsed, timezone.utc)
                    client_local = user_localize_dt(request.user, parsed.astimezone(timezone.utc))
                    if client_local.date() == (log_date - timedelta(days=1)):
                        return log_date - timedelta(days=1)
                except Exception:
                    pass
        return log_date

    """
    POST /api/nutra-logs            – single entry or list
    GET  /api/nutra-logs            – today's log
    GET  /api/nutra-logs?date=YYYY-MM-DD
    """
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _adult_food_counts_for_engine(user, log_date):
        entries = NutraEntry.objects.filter(
            session__user=user,
            session__date=log_date,
            food__isnull=False,
        ).select_related("module")
        disc = []
        muscle = []
        for e in entries:
            module = getattr(e, "module", None)
            module_name = str(getattr(module, "name", "") or "").lower()
            module_cat = str(getattr(module, "nutrition_category", "") or "").lower()
            score = float(e.score or 0)
            if module_cat == "disc" or any(t in module_name for t in ("disc", "lubric", "spine")):
                disc.append(score)
            elif module_cat == "muscle" or any(t in module_name for t in ("muscle", "repair", "fuel")):
                muscle.append(score)
        selected = sorted(disc, reverse=True)[:2] + sorted(muscle, reverse=True)[:2]
        return sum(selected)

    def list(self, request):
        d = request.query_params.get("date")
        try:
            log_date = dt.fromisoformat(d) if d else user_today(request.user)
        except Exception:
            return Response({"detail": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        session = (
            NutraSession.objects
            .filter(user=request.user, date=log_date)
            .prefetch_related("entries__food", "entries__activity")
            .first()
        )

        data = NutraSessionSerializer(session).data if session else {}
        return Response({"date": str(log_date), "session": data})

    def create(self, request):
        try:
            age = get_user_age(request.user)
        except Exception:
            age = 0
        subscription_data = check_subscription_or_response(request.user).data
        if age >= 21 and not bool(subscription_data.get("is_paid", False)) and not bool(getattr(settings, "ADULT_PAYWALL_DISABLED", False)):
            return Response(
                {
                    "detail": "Nutrition/lifestyle logging is locked for free adult accounts.",
                    "paywall_required": True,
                    "gate": "adult_diagnosis_gate",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        raw = request.data
        data = raw.get("food_activity", raw)
        many = isinstance(data, list)

        write_ser = NutraEntryWriteSerializer(data=data, many=many)
        write_ser.is_valid(raise_exception=True)
        validated_items = write_ser.validated_data if many else [write_ser.validated_data]

        log_date = self._resolve_log_date(request)
        session, _ = NutraSession.objects.get_or_create(user=request.user, date=log_date)

        existing_entries = NutraEntry.objects.filter(session=session)
        # For Issue 13 (teen cap): capture raw traceable food points *before* adding this payload.
        raw_food_before = 0.0
        if age < 21:
            try:
                raw_food_before = float(
                    existing_entries.filter(food__isnull=False).aggregate(total=Sum("score"))["total"] or 0.0
                )
            except Exception:
                raw_food_before = 0.0
        now = timezone.now()

        def is_duplicate(entry):
            food = entry.get("food") or entry.get("food_id")
            activity = entry.get("activity") or entry.get("activity_id")

            # If it's a model instance, extract ID
            if hasattr(food, 'id'):
                food = food.id
            if hasattr(activity, 'id'):
                activity = activity.id

            # Duplicate protection is only to prevent accidental double-submits.
            # Users must be allowed to intentionally log the same food repeatedly.
            window_start = now - timedelta(seconds=2)
            if food:
                return existing_entries.filter(
                    food_id=int(food),
                    completed_at__gte=window_start,
                ).exists()
            if activity:
                return existing_entries.filter(
                    activity_id=int(activity),
                    completed_at__gte=window_start,
                ).exists()
            return False

        # Filter out duplicates
        cleaned_data = [entry for entry in validated_items if not is_duplicate(entry)]

        # Save only non-duplicate entries
        entries = []
        for entry in cleaned_data:
            entry_payload = dict(entry)
            entry_payload.pop("client_timestamp", None)
            entries.append(NutraEntry.objects.create(session=session, **entry_payload))
        for nentry in entries:
            if nentry.food_id:
                apply_engine_routing(
                    user=request.user,
                    log_date=session.date,
                    age_exact=age,
                    points=(nentry.score or 0),
                    entry_kind="food",
                )
            elif nentry.activity_id:
                apply_engine_routing(
                    user=request.user,
                    log_date=session.date,
                    age_exact=age,
                    points=(nentry.score or 0),
                    entry_kind="lifestyle",
                )
        # Spec alignment UX: make dashboard numbers update immediately after logging.
        # This rebuild applies routing + caps into DailyLog/HeightLedger for the log date.
        rebuild_ledger_from_date(request.user, log_date)
        read_ser = NutraEntryReadSerializer(entries, many=True)

        # Return totals for resolved log date (supports grace-period backdate).
        today = log_date
        today_entries = NutraEntry.objects.filter(
            session__user=request.user,
            session__date=today,
        ).select_related('food', 'activity')

        total_today_score = today_entries.aggregate(total=Sum('score'))['total'] or 0
        total_today_food_score = today_entries.filter(food__isnull=False).aggregate(total=Sum('score'))['total'] or 0
        today_log = NutraEntryReadSerializer(today_entries, many=True).data

        cleaned_log = [
            {
                "name": entry["item"]["name"],
                "score": entry["score"],
                "short_name": entry["item"].get("short_name", entry["item"]["short_name"])
            }
            for entry in today_log
        ]
        # print(total_today_score)
        # print(cleaned_log)
        exercise_logged_today = WorkoutEntry.objects.filter(
            session__user=request.user,
            session__date=log_date,
        ).exists()
        raw_food_points = float(total_today_food_score or 0)
        if age >= 21:
            effective_food_points = min(self._adult_food_counts_for_engine(request.user, log_date), 12.0) if exercise_logged_today else 0.0
            cap_limit = 12.0
        else:
            effective_food_points = min(raw_food_points, 35.0) if exercise_logged_today else 0.0
            cap_limit = 35.0
        counts_toward_engine = bool(exercise_logged_today and effective_food_points > 0)
        cap_reached = bool(raw_food_points >= cap_limit)
        diary_note = None
        teen_cap = None
        teen_cap_modal_required = False
        teen_cap_crossed_today = False
        teen_cap_message = None
        # Issue 13 teen safety copy + once/day gating.
        if age < 21:
            # Determine whether the user crossed the cap on this request.
            raw_food_after = float(raw_food_points or 0.0)
            modal_required = False
            try:
                crossed = bool(raw_food_before < 35.0 <= raw_food_after)
                if crossed:
                    _, created = NotificationEventLog.objects.get_or_create(
                        user=request.user,
                        event_key=TEEN_CAP_EVENT_KEY,
                        event_date=log_date,
                        defaults={"payload": {"raw_before": raw_food_before, "raw_after": raw_food_after}},
                    )
                    modal_required = bool(created)
            except Exception:
                modal_required = False
            teen_cap = teen_cap_result(raw_before=raw_food_before, raw_after=raw_food_after, modal_required=modal_required)
            teen_cap_modal_required = bool(teen_cap.modal_required)
            teen_cap_crossed_today = bool(teen_cap.crossed_today)
            teen_cap_message = teen_cap.message
            # Replace any existing cap copy with the exact spec string when cap is reached.
            diary_note = teen_cap_message
        elif cap_reached:
            diary_note = (
                f"You've maxed traceable nutrition points for today ({int(cap_limit)}). "
                "You can keep logging for personal tracking, but extra logs won’t increase traceable points."
            )
        daily = DailyLog.objects.filter(user=request.user, log_date=log_date).first()
        # Raw totals can keep increasing (diary/tracking), but traceable points must cap.
        # Adults: engine-countable nutrition already capped (12) and depends on exercise gate.
        # Teens: traceable nutrition points cap at 35 (even if users keep logging).
        traceable_food_points = min(raw_food_points, cap_limit)
        daily_nutrition_pts_today = int(round(effective_food_points if age >= 21 else traceable_food_points))
        daily_posture_pts_today = int((daily.engine1_points if daily else 0) or 0)
        daily_hgh_pts_today = int((daily.engine2_points if daily else 0) or 0)
        daily_lifestyle_pts_today = int((daily.lifestyle_points if daily else 0) or 0)

        payload = {
            "logged": True,
            "log_date": str(log_date),
            "counts_toward_engine": counts_toward_engine,
            "daily_posture_pts_today": daily_posture_pts_today,
            "daily_hgh_pts_today": daily_hgh_pts_today,
            "daily_nutrition_pts_today": daily_nutrition_pts_today,
            "daily_lifestyle_pts_today": daily_lifestyle_pts_today,
            "exercises_done": bool(exercise_logged_today),
            "cap_reached": cap_reached,
            "cap_limit": cap_limit,
            "diary_note": diary_note,
            # Issue 13 explicit fields (teen-only message + once/day modal gating).
            "teen_nutrition_cap_reached": bool(age < 21 and bool(teen_cap_message)),
            "teen_nutrition_cap_message": teen_cap_message if age < 21 else None,
            "teen_nutrition_cap_crossed_today": teen_cap_crossed_today if age < 21 else None,
            "teen_nutrition_cap_modal_required": teen_cap_modal_required if age < 21 else None,
            "nutrition": read_ser.data,
            "nutrastion": read_ser.data,
            # Backward-compat: keep raw totals, but also provide capped totals for UI.
            # Historically this key was used by clients as "today nutrition points".
            # Use FOOD-only traceable points here to avoid mixing lifestyle points into nutrition totals.
            "today_total_nutrition_score": float(traceable_food_points),
            "today_total_nutrition_score_all": float(total_today_score or 0),
            "today_total_food_score": total_today_food_score,
            "today_total_food_score_traceable": float(traceable_food_points),
            "today_total_food_score_raw": float(raw_food_points),
            "today_logged_nutrition": cleaned_log,
        }

        return Response(payload, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        """
        PATCH /api/nutra-logs/{id}/
        Spec 14.2: editing a past log must rebuild HeightLedger from that date forward.
        """
        if not pk:
            return Response({"detail": "id is required"}, status=status.HTTP_400_BAD_REQUEST)
        entry = (
            NutraEntry.objects.filter(pk=pk, session__user=request.user)
            .select_related("session", "module", "food", "activity")
            .first()
        )
        if not entry:
            return Response({"detail": "Nutrition entry not found"}, status=status.HTTP_404_NOT_FOUND)
        log_date = entry.session.date

        # Allow updating servings/score only. (Changing food/activity would change routing semantics.)
        if "servings" in request.data:
            entry.servings = str(request.data.get("servings") or "")
        if "score" in request.data:
            try:
                v = request.data.get("score")
                entry.score = None if (v is None or v == "") else max(0, int(v))
            except Exception:
                return Response({"detail": "Invalid score"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            entry.save()
            out = rebuild_ledger_from_date(request.user, log_date)

        return Response(
            {
                "ok": True,
                "log_date": str(log_date),
                "rebuilt_from": out.get("from_date"),
                "days_rebuilt": out.get("days_rebuilt"),
                "entry": NutraEntryReadSerializer(entry).data,
            },
            status=status.HTTP_200_OK,
        )

    def update(self, request, pk=None):
        return self.partial_update(request, pk=pk)

    def destroy(self, request, pk=None):
        """
        DELETE /api/nutra-logs/{id}/
        Spec 14.2: deleting a past log must rebuild HeightLedger from that date forward.
        """
        if not pk:
            return Response({"detail": "id is required"}, status=status.HTTP_400_BAD_REQUEST)
        entry = (
            NutraEntry.objects.filter(pk=pk, session__user=request.user)
            .select_related("session")
            .first()
        )
        if not entry:
            return Response({"detail": "Nutrition entry not found"}, status=status.HTTP_404_NOT_FOUND)
        log_date = entry.session.date

        with transaction.atomic():
            entry.delete()
            out = rebuild_ledger_from_date(request.user, log_date)

        return Response(
            {
                "ok": True,
                "deleted": True,
                "log_date": str(log_date),
                "rebuilt_from": out.get("from_date"),
                "days_rebuilt": out.get("days_rebuilt"),
            },
            status=status.HTTP_200_OK,
        )