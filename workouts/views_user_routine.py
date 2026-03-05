from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Prefetch
from .models import UserRoutine, UserRoutineExercise
from .serializers_user_routine import UserRoutineSerializer


class UserRoutineListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        routine_type = request.query_params.get("routine_type")

        routines_qs = UserRoutine.objects.filter(
            user=request.user,
            is_active=True
        ).order_by("-created_at")

        if routine_type in ["posture", "hgh"]:
            routines_qs = routines_qs.filter(routine_type=routine_type)

        if not routines_qs.exists():
            return Response({"detail": "No routines found"}, status=404)

        # Prefetch exercises with related exercise data
        routines_qs = routines_qs.prefetch_related(
            Prefetch("exercises", queryset=UserRoutineExercise.objects.select_related("exercise"))
        )

        # If a routine_type is provided, return only the latest one
        if routine_type in ["posture", "hgh"]:
            routine = routines_qs.first()
            serializer = UserRoutineSerializer(routine, context={"request": request})
            return Response(serializer.data)

        # Otherwise return all routines as a list
        serializer = UserRoutineSerializer(routines_qs, many=True, context={"request": request})
        return Response(serializer.data)
