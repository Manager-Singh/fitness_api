# workouts/views_plan.py
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from workouts.models import Track
from .models import RoutineVariant
from .serializers_plan import RoutinePlanSerializer
from utils.age import get_user_age
from utils.check_payment import check_subscription_or_response


# class MyWorkoutPlanView(APIView):
#     """
#     GET /api/my-workouts  → personalised routines for the logged-in user
#     """
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         # 1. age
#         try:
#             age = get_user_age(request.user)
#         except Exception as exc:
#             return Response({"detail": str(exc)},
#                             status=status.HTTP_400_BAD_REQUEST)

#         # 2. variants for that age
#         variants = (
#             RoutineVariant.objects
#             .select_related("template", "age_bracket")
#             .prefetch_related("prescriptions__exercise")
#             .filter(age_bracket__min_age__lte=age)
#             .filter(
#                 Q(age_bracket__max_age__isnull=True) |
#                 Q(age_bracket__max_age__gte=age)
#             )
#         )

#         # 3. pass request into serializer context  ↓↓↓
#         data = RoutinePlanSerializer(
#             variants,
#             many=True,
#             context={"request": request},      # ★ key line
#         ).data

#         return Response({"age": age, "routines": data})


class MyWorkoutPlanView(APIView):
    """
    GET /api/my-workouts?track=posture → includes 'ess' and 'pos'
    GET /api/my-workouts?track=hgh     → includes only 'hgh'
    GET /api/my-workouts               → all routines
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            age = get_user_age(request.user)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        subscription_data = check_subscription_or_response(request.user).data
        if age >= 21 and not bool(subscription_data.get("is_paid", False)):
            return Response(
                {
                    "detail": "Workout plan is locked for free adult accounts.",
                    "paywall_required": True,
                    "gate": "adult_diagnosis_gate",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # input: 'posture' or 'hgh'
        track_group = request.query_params.get("track")

        # mapping group name to actual track codes
        track_map = {
            "posture": [Track.ESSENTIALS, Track.POSTURE],
            "hgh": [Track.HGH],
        }

        if track_group and track_group not in track_map:
            return Response({"detail": f"Invalid track group '{track_group}'"}, status=400)

        variants = (
            RoutineVariant.objects
            .select_related("template", "age_bracket")
            .prefetch_related("prescriptions__exercise")
            .filter(age_bracket__min_age__lte=age)
            .filter(
                Q(age_bracket__max_age__isnull=True) |
                Q(age_bracket__max_age__gte=age)
            )
        )

        # apply group-based filter
        if track_group:
            variants = variants.filter(track__in=track_map[track_group])

        data = RoutinePlanSerializer(
            variants,
            many=True,
            context={"request": request}
        ).data

        return Response({
            "age": age,
            "track": track_group or "all",
            "routines": data
        })