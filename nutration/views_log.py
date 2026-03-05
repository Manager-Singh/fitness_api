from datetime import date as dt
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models_log import NutraSession, NutraEntry
from .serializers_log import (
    NutraEntryWriteSerializer, NutraEntryReadSerializer,
    NutraSessionSerializer
)

class NutraLogViewSet(viewsets.ViewSet):
    """
    POST /api/nutra-logs            – single entry or list
    GET  /api/nutra-logs            – today's log
    GET  /api/nutra-logs?date=YYYY-MM-DD
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        d = request.query_params.get("date")
        log_date = dt.fromisoformat(d) if d else timezone.localdate()

        session = (
            NutraSession.objects
            .filter(user=request.user, date=log_date)
            .prefetch_related("entries__food", "entries__activity")
            .first()
        )

        data = NutraSessionSerializer(session).data if session else {}
        return Response({"date": str(log_date), "session": data})

    def create(self, request):
        raw = request.data
        data = raw.get("food_activity", raw)
        many = isinstance(data, list)

        write_ser = NutraEntryWriteSerializer(data=data, many=many)
        write_ser.is_valid(raise_exception=True)

        session, _ = NutraSession.objects.get_or_create(
            user=request.user, date=timezone.localdate()
        )

        existing_entries = NutraEntry.objects.filter(session=session)
        existing_food_ids = set(existing_entries.exclude(food=None).values_list('food_id', flat=True))
        existing_activity_ids = set(existing_entries.exclude(activity=None).values_list('activity_id', flat=True))

        def is_duplicate(entry):
            food = entry.get("food") or entry.get("food_id")
            activity = entry.get("activity") or entry.get("activity_id")

            # If it's a model instance, extract ID
            if hasattr(food, 'id'):
                food = food.id
            if hasattr(activity, 'id'):
                activity = activity.id

            return (
                (food and int(food) in existing_food_ids) or
                (activity and int(activity) in existing_activity_ids)
            )

        # Filter out duplicates
        cleaned_data = [entry for entry in write_ser.validated_data if not is_duplicate(entry)]

        # Save only non-duplicate entries
        entries = [NutraEntry.objects.create(session=session, **entry) for entry in cleaned_data]
        read_ser = NutraEntryReadSerializer(entries, many=True)

        # ── Today’s nutrition logs ──
        today = dt.today()
        today_entries = NutraEntry.objects.filter(
            session__user=request.user,
            session__date=today,
            food__isnull=False
        ).select_related('food')

        total_today_score = today_entries.aggregate(total=Sum('score'))['total'] or 0
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
        payload = {
            "nutrastion": read_ser.data,
            "today_total_nutrition_score": total_today_score,
            "today_logged_nutrition": cleaned_log,
        }

        return Response(payload, status=status.HTTP_201_CREATED)