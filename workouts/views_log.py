# workouts/views_log.py
from datetime import date as dt
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Count

from .models import WorkoutSession, UserRoutine
from .serializers_log import (
    WorkoutEntryWriteSerializer,
    WorkoutEntryReadSerializer,
    WorkoutSessionSerializer,
)
from utils.age import get_user_age 


class WorkoutLogViewSet(viewsets.ViewSet):
    """
    POST   /api/workout-logs           — add finished exercise
    GET    /api/workout-logs           — today’s session(s)
    GET    /api/workout-logs/?date=YYYY-MM-DD  — specific day
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        date_q = request.query_params.get("date")
        log_date = dt.fromisoformat(date_q) if date_q else timezone.localdate()

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
        today = timezone.localdate()
        user_routine_id = request.data.get("user_routine")
        if not user_routine_id:
            return Response({"detail": "user_routine is required"},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            user_routine = UserRoutine.objects.get(pk=user_routine_id, user=request.user)
        except UserRoutine.DoesNotExist:
            return Response({"detail": "UserRoutine not found"},
                            status=status.HTTP_404_NOT_FOUND)

        # Get user age
        try:
            age = get_user_age(request.user)
        except Exception:
            age = None

        # Restrict adults (>21) to max 8 exercises/day
        if age is not None and age > 21:
            session = WorkoutSession.objects.filter(
                user=request.user, date=today
            ).prefetch_related("entries").first()

            existing_logs = session.entries.count() if session else 0
            if existing_logs >= 8:
                return Response(
                    {"detail": "Exercise limit reached. Adults (age > 21) can log up to 8 exercises per day."},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Create or get session for today
        session, _ = WorkoutSession.objects.get_or_create(
            user=request.user,
            user_routine=user_routine,
            date=today,
        )

        # Save new entry
        ser = WorkoutEntryWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        entry = ser.save(session=session)

        # Count total workouts logged today
        total_workouts_today = WorkoutSession.objects.filter(
            user=request.user,
            date=today
        ).aggregate(total=Count("entries"))["total"] or 0

        return Response({
            "entry": WorkoutEntryReadSerializer(entry).data,
            "total_workouts_today": total_workouts_today
        }, status=status.HTTP_201_CREATED)
