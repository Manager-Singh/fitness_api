from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from habits.services import (
    build_habits_plan_payload,
    capped_habit_points_for_engine,
    log_habit,
    resolve_habit_log_date,
    total_raw_habit_points,
    DAILY_HABIT_CAP,
)
from habits.serializers import HabitLogWriteSerializer
from users.spec_runtime import rebuild_ledger_from_date
from utils.user_time import user_today


class HabitCatalogView(APIView):
    """GET /api/habits — catalog + today's slot completion."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        log_date = request.query_params.get("date")
        if log_date:
            try:
                from datetime import date as dt

                parsed = dt.fromisoformat(str(log_date))
            except Exception:
                return Response(
                    {"detail": "Invalid date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            parsed = user_today(request.user)
        return Response(build_habits_plan_payload(request.user, parsed))


class HabitLogViewSet(viewsets.ViewSet):
    """
    POST /api/habit-logs — log AM/PM/once micro-habit (Engine 1, cap 6/day).
    GET  /api/habit-logs — today's habit state (same shape as habits catalog).
    """

    permission_classes = [IsAuthenticated]

    def list(self, request):
        date_q = request.query_params.get("date")
        if date_q:
            try:
                from datetime import date as dt

                log_date = dt.fromisoformat(date_q)
            except Exception:
                return Response(
                    {"detail": "Invalid date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            log_date = user_today(request.user)
        return Response(build_habits_plan_payload(request.user, log_date))

    def create(self, request):
        ser = HabitLogWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        log_date = resolve_habit_log_date(request.user, request.data)

        try:
            entry, created = log_habit(
                request.user,
                log_date,
                data["habit_code"],
                data["slot"],
            )
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                detail = exc.message_dict
            elif hasattr(exc, "messages"):
                detail = list(exc.messages)
            else:
                detail = str(exc)
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

        rebuild_ledger_from_date(request.user, log_date)

        raw_pts = total_raw_habit_points(request.user, log_date)
        return Response(
            {
                "logged": True,
                "created": created,
                "updated": not created,
                "log_date": str(log_date),
                "habit_code": entry.habit.code,
                "slot": entry.slot,
                "points": int(entry.points),
                "habit_points_today": raw_pts,
                "habit_points_capped_for_engine": capped_habit_points_for_engine(
                    request.user, log_date
                ),
                "daily_cap": DAILY_HABIT_CAP,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
