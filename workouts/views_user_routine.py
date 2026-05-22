from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Prefetch
from django.conf import settings
from .models import UserRoutine, UserRoutineExercise
from .serializers_user_routine import UserRoutineSerializer
from posture.models import PostureReport
from utils.routine_genrate import generate_user_routines
from utils.posture.height_constants import POSTURE_SEGMENT_MAX_LOSS_CM, posture_segment_opt_pct
from posture_questions.services.routine_service import RoutineService
from utils.check_payment import check_subscription_or_response
from utils.age import get_user_age


class UserRoutineListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Section 7.1: adult free users cannot access workout plan.
        try:
            age = int(get_user_age(request.user) or 0)
        except Exception:
            age = 0
        sub = check_subscription_or_response(request.user).data
        if age >= 21 and not bool(sub.get("is_paid", False)) and not bool(getattr(settings, "ADULT_PAYWALL_DISABLED", False)):
            return Response(
                {
                    "detail": "Workout plan is locked for free adult accounts.",
                    "paywall_required": True,
                    "gate": "adult_diagnosis_gate",
                },
                status=403,
            )

        def _default_breakdown():
            out = {}
            for seg, mx in POSTURE_SEGMENT_MAX_LOSS_CM.items():
                cur = round(float(mx) * 0.5, 2)
                out[seg] = {
                    "current_loss_cm": cur,
                    "max_loss_cm": mx,
                    "percent_optimized": posture_segment_opt_pct(cur, mx),
                }
            return out

        routine_type = request.query_params.get("routine_type")

        routines_qs = UserRoutine.objects.filter(
            user=request.user,
            is_active=True
        ).order_by("-created_at")

        if routine_type in ["posture", "hgh"]:
            routines_qs = routines_qs.filter(routine_type=routine_type)

        if not routines_qs.exists():
            latest_report = PostureReport.objects.filter(user=request.user).order_by("-created_at").first()
            breakdown = None
            if latest_report and isinstance(latest_report.data, dict):
                breakdown = latest_report.data.get("optimization_breakdown")
            if not breakdown:
                breakdown = _default_breakdown()
            breakdown = RoutineService.reconciled_optimization_breakdown(
                request.user, breakdown
            )
            generate_user_routines(request.user, breakdown)
            routines_qs = UserRoutine.objects.filter(
                user=request.user,
                is_active=True
            ).order_by("-created_at")
            if routine_type in ["posture", "hgh"]:
                routines_qs = routines_qs.filter(routine_type=routine_type)
            if not routines_qs.exists():
                return Response({"detail": "No routines found"}, status=404)

        # Spec guard for teens: if routines contain mixed-category exercises, rebuild routines.
        if age < 21:
            routines = list(
                routines_qs.prefetch_related(
                    Prefetch("exercises", queryset=UserRoutineExercise.objects.select_related("exercise"))
                )
            )
            posture = next((r for r in routines if str(r.routine_type).lower() == "posture"), None)
            hgh = next((r for r in routines if str(r.routine_type).lower() == "hgh"), None)

            def _has_wrong_category(routine, allowed):
                if not routine:
                    return False
                for ure in routine.exercises.all():
                    cat = str(getattr(ure.exercise, "category", "") or "").lower()
                    if cat not in allowed:
                        return True
                return False

            posture_bad = _has_wrong_category(posture, {"posture", "general", "hgh"})
            if posture_bad:
                latest_report = PostureReport.objects.filter(user=request.user).order_by("-created_at").first()
                breakdown = None
                if latest_report and isinstance(latest_report.data, dict):
                    breakdown = latest_report.data.get("optimization_breakdown")
                if not breakdown:
                    breakdown = _default_breakdown()
                breakdown = RoutineService.reconciled_optimization_breakdown(
                    request.user, breakdown
                )
                generate_user_routines(request.user, breakdown)
                routines_qs = UserRoutine.objects.filter(
                    user=request.user,
                    is_active=True
                ).order_by("-created_at")

        # Prefetch exercises with related exercise data
        routines_qs = routines_qs.prefetch_related(
            Prefetch("exercises", queryset=UserRoutineExercise.objects.select_related("exercise"))
        )

        # If a routine_type is provided, return only the latest one
        if routine_type in ["posture", "hgh"]:
            routine = routines_qs.first()
            serializer = UserRoutineSerializer(routine, context={"request": request})
            return Response(serializer.data)

        # Teen UX: unified 10-exercise POSTURE routine (legacy MIXED merge if old HGH row still active).
        if age < 21:
            routines = list(routines_qs)
            posture = next((r for r in routines if str(r.routine_type).lower() == "posture"), None)
            hgh = next((r for r in routines if str(r.routine_type).lower() == "hgh"), None)
            if posture and not hgh:
                serializer = UserRoutineSerializer(posture, context={"request": request})
                return Response(serializer.data)
            if posture or hgh:
                mixed_routine_id = posture.id if posture else (hgh.id if hgh else None)
                merged_exercises = []
                merged_created_at = None
                merged_updated_at = None
                for r in [posture, hgh]:
                    if not r:
                        continue
                    if merged_created_at is None or r.created_at < merged_created_at:
                        merged_created_at = r.created_at
                    if merged_updated_at is None or r.updated_at > merged_updated_at:
                        merged_updated_at = r.updated_at
                    r_data = UserRoutineSerializer(r, context={"request": request}).data
                    for ex in r_data.get("exercises", []) or []:
                        ex["source_routine_type"] = r_data.get("routine_type")
                        ex["user_routine_id"] = mixed_routine_id
                        ex["source_user_routine_id"] = r_data.get("id")
                        ex["routine_id"] = mixed_routine_id
                        ex["source_routine_id"] = r_data.get("id")
                        merged_exercises.append(ex)
                merged_exercises.sort(
                    key=lambda e: (
                        0 if str(e.get("source_routine_type", "")).lower() == "posture" else 1,
                        int(e.get("order") or 0),
                        int(e.get("id") or 0),
                    )
                )
                return Response({
                    "id": mixed_routine_id,
                    "routine_type": "MIXED",
                    "created_at": merged_created_at,
                    "updated_at": merged_updated_at,
                    "is_active": True,
                    "exercises": merged_exercises,
                })

        # Otherwise return all routines as a list
        serializer = UserRoutineSerializer(routines_qs, many=True, context={"request": request})
        return Response(serializer.data)
