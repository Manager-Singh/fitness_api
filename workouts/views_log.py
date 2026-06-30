# workouts/views_log.py
from datetime import date as dt, datetime, timedelta
from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Sum
from django.db import transaction

from .models import WorkoutSession, UserRoutine
from .serializers_log import (
    WorkoutEntryWriteSerializer,
    WorkoutEntryReadSerializer,
    WorkoutSessionSerializer,
)
from utils.age import get_user_age 
from utils.paywall_flags import is_teen_age
from utils.engine_routing import apply_engine_routing
from utils.check_payment import check_subscription_or_response
from utils.monetization_gate import logging_locked_payload
from users.models import DailyLog
from utils.user_time import user_localize_dt, user_today
from workouts.models import UserRoutineExercise
from users.spec_runtime import rebuild_ledger_from_date
from utils.dashboard_new_embed import build_dashboard_new_embed
from workouts.models import WorkoutEntry, WorkoutSetCompletion
from nutration.models_log import NutraEntry
from workouts.set_progress import (
    completed_set_count,
    count_fully_completed_assignments,
    credited_points_for_day,
    expected_sets_for_assignment,
    per_set_points,
    progress_for_assignment,
    workout_activity_exists,
)


class WorkoutLogViewSet(viewsets.ViewSet):
    """
    POST   /api/workout-logs           — add finished exercise
    GET    /api/workout-logs           — today’s session(s)
    GET    /api/workout-logs/?date=YYYY-MM-DD  — specific day
    """
    permission_classes = [IsAuthenticated]

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

    @staticmethod
    def _response_payload(
        request,
        *,
        log_date,
        age,
        entry,
        counts_toward_engine,
        duplicate=False,
        credited_set_index=None,
        points_credited=0,
    ):
        total_workouts_today = count_fully_completed_assignments(request.user, log_date)
        total_sets_completed_today = WorkoutSetCompletion.objects.filter(
            user=request.user,
            log_date=log_date,
        ).values("user_routine_exercise_id", "set_index").distinct().count()
        daily = DailyLog.objects.filter(user=request.user, log_date=log_date).first()
        daily_posture_pts_today = int((daily.engine1_points if daily else 0) or 0)
        daily_hgh_pts_today = int((daily.engine2_points if daily else 0) or 0)
        # Match POST /api/nutra-logs: capped traceable food from entries (DailyLog.food_points
        # stays 0 for many adults until engine rules; teens looked "correct" by coincidence).
        raw_food_pts = float(
            NutraEntry.objects.filter(
                session__user=request.user,
                session__date=log_date,
                food__isnull=False,
            ).aggregate(total=Sum("score"))["total"]
            or 0
        )
        if int(age or 0) >= 21:
            from utils.adult_nutrition import adult_disc_muscle_food_id_sets, adult_engine_nutrition_points

            exercise_any = workout_activity_exists(request.user, log_date)
            posture_pts = float(credited_points_for_day(request.user, log_date, routine_type="posture"))
            entries = NutraEntry.objects.filter(
                session__user=request.user,
                session__date=log_date,
                food__isnull=False,
            ).select_related("module")
            d_ids, m_ids = adult_disc_muscle_food_id_sets(entries)
            traceable = adult_engine_nutrition_points(posture_pts, d_ids, m_ids) if exercise_any else 0.0
            daily_nutrition_pts_today = int(round(traceable))
        else:
            cap_limit = 35.0
            daily_nutrition_pts_today = int(round(min(raw_food_pts, cap_limit)))
        daily_lifestyle_pts_today = int((daily.lifestyle_points if daily else 0) or 0)

        payload = {
            "logged": True,
            "duplicate": bool(duplicate),
            "log_date": str(log_date),
            "counts_toward_engine": bool(counts_toward_engine),
            "daily_posture_pts_today": daily_posture_pts_today,
            "daily_hgh_pts_today": daily_hgh_pts_today,
            "daily_nutrition_pts_today": daily_nutrition_pts_today,
            "daily_lifestyle_pts_today": daily_lifestyle_pts_today,
            "exercises_done": bool(total_workouts_today > 0),
            "entry": WorkoutEntryReadSerializer(entry, context={"request": request}).data,
            "total_workouts_today": total_workouts_today,
            "total_sets_completed_today": total_sets_completed_today,
            "credited_set_index": credited_set_index,
            "points_credited": float(points_credited or 0),
        }
        ure = getattr(entry, "user_routine_exercise", None)
        if ure is not None:
            progress = progress_for_assignment(request.user, log_date, ure)
            payload.update(
                {
                    "completed_sets": progress["completed_sets"],
                    "total_sets": progress["total_sets"],
                    "progress_fraction": progress["progress_fraction"],
                    "partially_completed": progress["partially_completed"],
                    "exercise_completed": progress["completed"],
                }
            )
        payload["dashboard_new"] = build_dashboard_new_embed(request.user, log_date, request=request)
        return payload

    def list(self, request):
        date_q = request.query_params.get("date")
        try:
            log_date = dt.fromisoformat(date_q) if date_q else user_today(request.user)
        except Exception:
            return Response({"detail": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        sessions = WorkoutSession.objects.filter(
            user=request.user, date=log_date
        ).prefetch_related("entries__exercise", "user_routine")

        data = WorkoutSessionSerializer(sessions, many=True).data
        return Response({"date": str(log_date), "sessions": data})

    def create(self, request):
        """
        Expected JSON:
        {
            "user_routine": 3,
            "exercise_id": 5,
            "points": 15,
            "sets_done": 2,
            "reps_done": 20,
            "duration_s": 60
        }
        """
        log_date = self._resolve_log_date(request)
        user_routine_id = request.data.get("user_routine")
        if not user_routine_id:
            return Response({"detail": "user_routine is required"},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            user_routine = UserRoutine.objects.get(pk=user_routine_id, user=request.user)
        except UserRoutine.DoesNotExist:
            return Response({"detail": "UserRoutine not found"}, status=status.HTTP_404_NOT_FOUND)

        # Get user age
        try:
            age = get_user_age(request.user)
        except Exception:
            age = 0
        is_teen = is_teen_age(age_years=age, user=request.user)
        subscription_data = check_subscription_or_response(request.user).data
        locked = logging_locked_payload(
            request.user,
            detail="Exercise logging is locked. Subscribe to unlock full access.",
        )
        if locked:
            return Response(locked, status=status.HTTP_403_FORBIDDEN)

        # Spec alignment: no hard per-day logging cap here.

        # Create or get session for today
        session, _ = WorkoutSession.objects.get_or_create(
            user=request.user,
            user_routine=user_routine,
            date=log_date,
        )

        # Save new entry
        ser = WorkoutEntryWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        exercise = ser.validated_data.get("exercise")

        # Teen UX: `/api/my-routine` returns a single MIXED routine id, but exercises may
        # physically belong to POSTURE or HGH routines. Auto-route the log accordingly.
        if exercise and not UserRoutineExercise.objects.filter(routine=user_routine, exercise=exercise).exists():
            if is_teen:
                fallback_routine = (
                    UserRoutine.objects.filter(user=request.user, is_active=True)
                    .exclude(id=user_routine.id)
                    .filter(exercises__exercise=exercise)
                    .distinct()
                    .first()
                )
                if fallback_routine:
                    user_routine = fallback_routine
                    # Ensure session exists for the routed routine (unique per user+routine+date).
                    session, _ = WorkoutSession.objects.get_or_create(
                        user=request.user,
                        user_routine=user_routine,
                        date=log_date,
                    )
                else:
                    return Response(
                        {"detail": "Exercise is not assigned in this routine."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return Response(
                    {"detail": "Exercise is not assigned in this routine."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        routine_type = str(getattr(user_routine, "routine_type", "") or "").lower()
        entry_payload = dict(ser.validated_data)
        requested_set_index = entry_payload.pop("set_index", None)
        entry_payload.pop("completion_kind", None)
        entry_payload.pop("client_timestamp", None)
        # Ensure the logged entry is linked to the assigned routine exercise.
        # Dashboard progress counts distinct `user_routine_exercise_id` completions.
        assigned_ure = None
        if exercise:
            assigned_ure = UserRoutineExercise.objects.filter(
                routine=user_routine,
                exercise=exercise,
            ).select_related("variant_exercise", "exercise").first()
            entry_payload["user_routine_exercise"] = assigned_ure
        if not assigned_ure:
            return Response(
                {"detail": "Exercise is not assigned in this routine."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        total_sets = expected_sets_for_assignment(assigned_ure, exercise=exercise)
        if requested_set_index is not None:
            try:
                requested_set_index = int(requested_set_index)
            except Exception:
                return Response({"detail": "Invalid set_index"}, status=status.HTTP_400_BAD_REQUEST)
            if requested_set_index < 1 or requested_set_index > total_sets:
                return Response(
                    {"detail": f"set_index must be between 1 and {total_sets}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            requested_set_indexes = [requested_set_index]
        elif entry_payload.get("sets_done") not in (None, ""):
            try:
                sets_done = max(0, int(entry_payload.get("sets_done") or 0))
            except Exception:
                return Response({"detail": "Invalid sets_done"}, status=status.HTTP_400_BAD_REQUEST)
            requested_set_indexes = list(range(1, min(sets_done, total_sets) + 1)) or [1]
        else:
            # Backward-compatible full-exercise completion for older clients.
            requested_set_indexes = list(range(1, total_sets + 1))

        duplicate_qs = session.entries.filter(user_routine_exercise=assigned_ure)
        existing_entry = duplicate_qs.order_by("created_at").first()
        with transaction.atomic():
            if existing_entry:
                entry = existing_entry
            else:
                entry_payload["points"] = int(getattr(exercise, "points", 0) or entry_payload.get("points") or 0)
                entry_payload["sets_done"] = 0
                entry = session.entries.create(**entry_payload)

            set_points = per_set_points(exercise, total_sets)
            created_indexes = []
            credited_points = Decimal("0.0000")
            for set_idx in requested_set_indexes:
                completion, created = WorkoutSetCompletion.objects.get_or_create(
                    user=request.user,
                    log_date=log_date,
                    user_routine_exercise=assigned_ure,
                    exercise=exercise,
                    set_index=set_idx,
                    defaults={
                        "session": session,
                        "workout_entry": entry,
                        "points_credited": set_points,
                    },
                )
                if created:
                    created_indexes.append(set_idx)
                    credited_points += set_points
                elif completion.workout_entry_id is None:
                    completion.workout_entry = entry
                    completion.session = session
                    completion.save(update_fields=["workout_entry", "session"])

            done_sets = completed_set_count(
                request.user,
                log_date,
                user_routine_exercise=assigned_ure,
                exercise=exercise,
            )
            entry.sets_done = min(done_sets, total_sets)
            entry.save(update_fields=["sets_done"])

        if not created_indexes:
            payload = self._response_payload(
                request,
                log_date=log_date,
                age=age,
                entry=entry,
                counts_toward_engine=False,
                duplicate=True,
                credited_set_index=requested_set_index,
                points_credited=0,
            )
            payload["message"] = "This workout set is already completed for today."
            return Response(payload, status=status.HTTP_200_OK)

        apply_engine_routing(
            user=request.user,
            log_date=log_date,
            age_exact=age,
            points=credited_points,
            routine_type=routine_type,
            entry_kind="exercise",
        )
        # Spec alignment UX: make dashboard numbers update immediately after logging.
        rebuild_ledger_from_date(request.user, log_date)
        payload = self._response_payload(
            request,
            log_date=log_date,
            age=age,
            entry=entry,
            counts_toward_engine=True,
            duplicate=False,
            credited_set_index=created_indexes[-1] if len(created_indexes) == 1 else None,
            points_credited=credited_points,
        )
        return Response(payload, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        """
        PATCH /api/workout-logs/{id}/
        Spec 14.2: editing a past log must rebuild HeightLedger from that date forward.
        """
        if not pk:
            return Response({"detail": "id is required"}, status=status.HTTP_400_BAD_REQUEST)
        entry = (
            WorkoutEntry.objects.filter(pk=pk, session__user=request.user)
            .select_related("session", "exercise")
            .first()
        )
        if not entry:
            return Response({"detail": "Workout entry not found"}, status=status.HTTP_404_NOT_FOUND)
        log_date = entry.session.date

        # Only allow updating the mutable fields; exercise identity is immutable here.
        if "points" in request.data:
            try:
                entry.points = max(0, int(request.data.get("points") or 0))
            except Exception:
                return Response({"detail": "Invalid points"}, status=status.HTTP_400_BAD_REQUEST)
        for k in ("sets_done", "reps_done", "duration_s"):
            if k in request.data:
                v = request.data.get(k)
                if v is None or v == "":
                    setattr(entry, k, None)
                else:
                    try:
                        setattr(entry, k, max(0, int(v)))
                    except Exception:
                        return Response({"detail": f"Invalid {k}"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            entry.save()
            out = rebuild_ledger_from_date(request.user, log_date)

        return Response(
            {
                "ok": True,
                "log_date": str(log_date),
                "rebuilt_from": out.get("from_date"),
                "days_rebuilt": out.get("days_rebuilt"),
                "entry": WorkoutEntryReadSerializer(entry).data,
            },
            status=status.HTTP_200_OK,
        )

    def update(self, request, pk=None):
        # Treat PUT as PATCH for this endpoint.
        return self.partial_update(request, pk=pk)

    def destroy(self, request, pk=None):
        """
        DELETE /api/workout-logs/{id}/
        Spec 14.2: deleting a past log must rebuild HeightLedger from that date forward.
        """
        if not pk:
            return Response({"detail": "id is required"}, status=status.HTTP_400_BAD_REQUEST)
        entry = (
            WorkoutEntry.objects.filter(pk=pk, session__user=request.user)
            .select_related("session")
            .first()
        )
        if not entry:
            return Response({"detail": "Workout entry not found"}, status=status.HTTP_404_NOT_FOUND)
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
