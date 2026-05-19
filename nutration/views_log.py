from collections import defaultdict
from datetime import date as dt, datetime, timedelta
from django.db.models import Sum
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ModuleFood
from .models_log import NutraSession, NutraEntry
from .scoring import module_food_score_for_user
from .serializers_log import (
    NutraEntryWriteSerializer, NutraEntryReadSerializer,
    NutraSessionSerializer
)
from utils.age import get_user_age
from utils.check_payment import check_subscription_or_response
from workouts.models import WorkoutEntry
from users.models import DailyLog
from users.models import NotificationEventLog
from utils.user_time import user_localize_dt, user_today
from users.spec_runtime import rebuild_ledger_from_date
from utils.dashboard_new_embed import build_dashboard_new_embed
from utils.adult_nutrition import (
    ADULT_NUTRITION_FOOD_SLOT_MAX,
    dedupe_adult_food_entries_for_session,
    is_adult_flat_food_user,
    toggle_adult_food_entry,
)
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
    def _adult_traceable_food_points(user, log_date, exercise_logged_today):
        """Adult flat nutrition: 1 pt per unique Disc + Muscle food, gated by posture work logged."""
        from utils.adult_nutrition import adult_disc_muscle_food_id_sets, adult_engine_nutrition_points

        posture_pts = 0.0
        if exercise_logged_today:
            posture_pts = float(
                WorkoutEntry.objects.filter(
                    session__user=user,
                    session__date=log_date,
                    session__user_routine__routine_type__iexact="posture",
                ).aggregate(total=Sum("points"))["total"]
                or 0.0
            )
        entries = NutraEntry.objects.filter(
            session__user=user,
            session__date=log_date,
            food__isnull=False,
        ).select_related("module")
        disc_ids, muscle_ids = adult_disc_muscle_food_id_sets(entries)
        return adult_engine_nutrition_points(posture_pts, disc_ids, muscle_ids)

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
        if is_adult_flat_food_user(request.user, age) and not bool(subscription_data.get("is_paid", False)) and not bool(getattr(settings, "ADULT_PAYWALL_DISABLED", False)):
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

        def _normalize_write_payload(item):
            """Accept legacy keys (food, module, activity) used by some clients/tests."""
            if not isinstance(item, dict):
                return item
            out = dict(item)
            if "food_id" not in out and out.get("food") is not None:
                out["food_id"] = out.pop("food")
            if "module_id" not in out and out.get("module") is not None:
                out["module_id"] = out.pop("module")
            if "activity_id" not in out and out.get("activity") is not None:
                out["activity_id"] = out.pop("activity")
            return out

        if isinstance(data, list):
            data = [_normalize_write_payload(x) for x in data]
        else:
            data = _normalize_write_payload(data)
        many = isinstance(data, list)

        write_ser = NutraEntryWriteSerializer(data=data, many=many)
        write_ser.is_valid(raise_exception=True)
        validated_items = write_ser.validated_data if many else [write_ser.validated_data]

        log_date = self._resolve_log_date(request)
        now = timezone.now()
        adult = is_adult_flat_food_user(request.user, age)
        raw_food_before = 0.0

        with transaction.atomic():
            session, _ = (
                NutraSession.objects.select_for_update()
                .get_or_create(user=request.user, date=log_date)
            )
            existing_entries = NutraEntry.objects.filter(session=session)

            if not adult:
                try:
                    raw_food_before = float(
                        existing_entries.filter(food__isnull=False).aggregate(total=Sum("score"))["total"] or 0.0
                    )
                except Exception:
                    raw_food_before = 0.0

            def is_duplicate(entry):
                food = entry.get("food") or entry.get("food_id")
                activity = entry.get("activity") or entry.get("activity_id")
                if hasattr(food, "id"):
                    food = food.id
                if hasattr(activity, "id"):
                    activity = activity.id
                if adult and food:
                    return False
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

            cleaned_data = [entry for entry in validated_items if not is_duplicate(entry)]

            if adult:
                food_groups = defaultdict(list)

                def _food_pk_from_entry(entry):
                    food = entry.get("food") or entry.get("food_id")
                    if not food:
                        return None
                    return int(food.id) if hasattr(food, "id") else int(food)

                non_food = []
                for entry in cleaned_data:
                    pk = _food_pk_from_entry(entry)
                    if pk is None:
                        non_food.append(entry)
                    else:
                        food_groups[pk].append(entry)
                collapsed = []
                for _fid, group in food_groups.items():
                    if len(group) % 2 == 1:
                        collapsed.append(group[-1])
                cleaned_data = collapsed + non_food

            for entry in cleaned_data:
                entry_payload = dict(entry)
                entry_payload.pop("client_timestamp", None)
                food = entry_payload.get("food") or entry_payload.get("food_id")
                if adult and food:
                    module = entry_payload.get("module")
                    module_id = int(module.id) if hasattr(module, "id") else int(module)
                    food_pk = int(food.id) if hasattr(food, "id") else int(food)
                    rel = ModuleFood.objects.filter(module_id=module_id, food_id=food_pk).first()
                    food_score = module_food_score_for_user(rel, request.user, age) if rel else 1
                    toggle_adult_food_entry(
                        session,
                        module_id=module_id,
                        food_id=food_pk,
                        servings=entry_payload.get("servings") or "",
                        score=food_score,
                    )
                    continue
                if adult:
                    module = entry_payload.get("module")
                    module_id = int(module.id) if hasattr(module, "id") else int(module)
                    food_pk = int(food.id) if hasattr(food, "id") else int(food)
                    rel = ModuleFood.objects.filter(module_id=module_id, food_id=food_pk).first()
                    entry_payload["score"] = module_food_score_for_user(rel, request.user, age) if rel else 1
                NutraEntry.objects.create(session=session, **entry_payload)

            if adult:
                dedupe_adult_food_entries_for_session(session)

            rebuild_ledger_from_date(request.user, log_date)

        # Return totals for resolved log date (supports grace-period backdate).
        today = log_date
        today_entries = NutraEntry.objects.filter(
            session__user=request.user,
            session__date=today,
        ).select_related('food', 'activity')

        read_ser = NutraEntryReadSerializer(today_entries, many=True)
        total_today_score = today_entries.aggregate(total=Sum('score'))['total'] or 0
        total_today_food_score = today_entries.filter(food__isnull=False).aggregate(total=Sum('score'))['total'] or 0
        today_log = read_ser.data

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
        if is_adult_flat_food_user(request.user, age):
            effective_food_points = self._adult_traceable_food_points(request.user, log_date, exercise_logged_today)
            cap_limit = float(ADULT_NUTRITION_FOOD_SLOT_MAX)
            cap_reached = bool(effective_food_points >= cap_limit)
        else:
            effective_food_points = min(raw_food_points, 35.0) if exercise_logged_today else 0.0
            cap_limit = 35.0
            cap_reached = bool(raw_food_points >= cap_limit)
        counts_toward_engine = bool(exercise_logged_today and effective_food_points > 0)
        diary_note = None
        teen_cap = None
        teen_cap_modal_required = False
        teen_cap_crossed_today = False
        teen_cap_message = None
        # Issue 13 teen safety copy + once/day gating.
        if not is_adult_flat_food_user(request.user, age):
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
        elif cap_reached and is_adult_flat_food_user(request.user, age):
            diary_note = (
                f"You've logged all {int(cap_limit)} traceable adult nutrition foods for today."
            )
        elif cap_reached:
            diary_note = (
                f"You've maxed traceable nutrition points for today ({int(cap_limit)}). "
                "You can keep logging for personal tracking, but extra logs won’t increase traceable points."
            )
        daily = DailyLog.objects.filter(user=request.user, log_date=log_date).first()
        # Raw totals can keep increasing (diary/tracking), but traceable points must cap.
        # daily_nutrition_pts_today matches today_total_nutrition_score (capped food traceable).
        # Engine eligibility stays on counts_toward_engine (uses effective_food_points + exercise).
        if is_adult_flat_food_user(request.user, age):
            traceable_food_points = float(effective_food_points)
        else:
            traceable_food_points = min(raw_food_points, cap_limit)
        daily_nutrition_pts_today = int(round(traceable_food_points))
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
            "teen_nutrition_cap_reached": bool(not is_adult_flat_food_user(request.user, age) and bool(teen_cap_message)),
            "teen_nutrition_cap_message": teen_cap_message if not is_adult_flat_food_user(request.user, age) else None,
            "teen_nutrition_cap_crossed_today": teen_cap_crossed_today if not is_adult_flat_food_user(request.user, age) else None,
            "teen_nutrition_cap_modal_required": teen_cap_modal_required if not is_adult_flat_food_user(request.user, age) else None,
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
        payload["dashboard_new"] = build_dashboard_new_embed(request.user, log_date)

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

        try:
            age = get_user_age(request.user)
        except Exception:
            age = 0

        # Allow updating servings/score only. (Changing food/activity would change routing semantics.)
        if "servings" in request.data:
            entry.servings = str(request.data.get("servings") or "")
        if "score" in request.data:
            if is_adult_flat_food_user(request.user, age) and entry.food_id:
                rel = entry.module.module_foods.filter(food_id=entry.food_id).first()
                entry.score = module_food_score_for_user(rel, request.user, age) if rel else 1
            else:
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