# workouts/views_log.py
from datetime import date as dt, datetime, timedelta
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Count
from django.db import transaction

from .models import WorkoutSession, UserRoutine
from .serializers_log import (
    WorkoutEntryWriteSerializer,
    WorkoutEntryReadSerializer,
    WorkoutSessionSerializer,
)
from utils.age import get_user_age 
from utils.engine_routing import apply_engine_routing
from utils.check_payment import check_subscription_or_response
from users.models import DailyLog
from utils.user_time import user_localize_dt, user_today
from workouts.models import UserRoutineExercise
from users.spec_runtime import rebuild_ledger_from_date
from workouts.models import WorkoutEntry


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
        subscription_data = check_subscription_or_response(request.user).data
        if age >= 21 and not bool(subscription_data.get("is_paid", False)):
            return Response(
                {
                    "detail": "Exercise logging is locked for free adult accounts.",
                    "paywall_required": True,
                    "gate": "adult_diagnosis_gate",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

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
            if age < 21:
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
        last_entry = (
            session.entries.filter(exercise=exercise).order_by("-created_at").first()
            if exercise else None
        )
        if last_entry and (timezone.now() - last_entry.created_at).total_seconds() < 60:
            return Response(
                {
                    "error": "duplicate_log",
                    "message": "This exercise was already logged within 60 seconds.",
                    "cooldown_s": 60,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        if age < 21 and routine_type == "hgh" and exercise:
            teen_hgh_exercise_count = session.entries.filter(exercise=exercise).count()
            if teen_hgh_exercise_count >= 2:
                return Response(
                    {
                        "error": "hgh_daily_exercise_cap_reached",
                        "message": "Max 2 completions per HGH exercise per day.",
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
        entry_payload = dict(ser.validated_data)
        entry_payload.pop("client_timestamp", None)
        # Ensure the logged entry is linked to the assigned routine exercise.
        # Dashboard progress counts distinct `user_routine_exercise_id` completions.
        if exercise:
            entry_payload["user_routine_exercise"] = UserRoutineExercise.objects.filter(
                routine=user_routine,
                exercise=exercise,
            ).first()
        entry = session.entries.create(**entry_payload)
        apply_engine_routing(
            user=request.user,
            log_date=log_date,
            age_exact=age,
            points=entry.points,
            routine_type=routine_type,
            entry_kind="exercise",
        )

        # Count total workouts logged today
        total_workouts_today = WorkoutSession.objects.filter(
            user=request.user,
            date=log_date
        ).aggregate(total=Count("entries"))["total"] or 0
        daily = DailyLog.objects.filter(user=request.user, log_date=log_date).first()
        daily_posture_pts_today = int((daily.engine1_points if daily else 0) or 0)
        daily_hgh_pts_today = int((daily.engine2_points if daily else 0) or 0)
        daily_nutrition_pts_today = int((daily.food_points if daily else 0) or 0)
        daily_lifestyle_pts_today = int((daily.lifestyle_points if daily else 0) or 0)

        return Response({
            "logged": True,
            "log_date": str(log_date),
            "counts_toward_engine": True,
            "daily_posture_pts_today": daily_posture_pts_today,
            "daily_hgh_pts_today": daily_hgh_pts_today,
            "daily_nutrition_pts_today": daily_nutrition_pts_today,
            "daily_lifestyle_pts_today": daily_lifestyle_pts_today,
            "exercises_done": bool(total_workouts_today > 0),
            "entry": WorkoutEntryReadSerializer(entry).data,
            "total_workouts_today": total_workouts_today
        }, status=status.HTTP_201_CREATED)

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
