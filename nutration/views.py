from django.db.models import Q, Sum
from rest_framework import viewsets,status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from utils.age import get_user_age

from .models import AgeGroup, Module, Food, ModuleFood
from .serializers import (
    AgeGroupSerializer, ModuleSerializer,
    FoodSerializer, ModuleFoodSerializer
)
from .serializers_plan import ModulePlanSerializer
from collections import defaultdict   # ← add this line
from .models_log import NutraEntry  # Adjust import as needed
from .serializers_log import (
    NutraEntryWriteSerializer, NutraEntryReadSerializer,
    NutraSessionSerializer
)
from datetime import date



class AgeGroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AgeGroup.objects.all()
    serializer_class = AgeGroupSerializer


class FoodViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Food.objects.all()
    serializer_class = FoodSerializer


class ModuleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    /api/modules/               list
    /api/modules/5/             detail
    /api/modules/by-age/25/     filter by age=25
    """
    queryset = Module.objects.select_related("age_group")
    serializer_class = ModuleSerializer

    @action(detail=False, url_path=r"by-age/(?P<age>\d+)")
    def by_age(self, request, age=None):
        age = int(age)
        qs = self.queryset.filter(
            age_group__min_age__lte=age
        ).filter(
            Q(age_group__max_age__isnull=True) |
            Q(age_group__max_age__gte=age)
        )

        page = self.paginate_queryset(qs)
        if page is not None:
            ser = self.get_serializer(page, many=True)
            return self.get_paginated_response(ser.data)

        return Response(self.get_serializer(qs, many=True).data)


class ModuleFoodViewSet(viewsets.ReadOnlyModelViewSet):
    """
    /api/module-foods/                  list
    /api/module-foods/by-module/3/      filter by module
    /api/module-foods/by-age/17/        items for an age
    """
    queryset = ModuleFood.objects.select_related(
        "module__age_group", "food"
    )
    serializer_class = ModuleFoodSerializer

    @action(detail=False, url_path=r"by-module/(?P<module_id>\d+)")
    def by_module(self, request, module_id=None):
        qs = self.queryset.filter(module_id=module_id)
        page = self.paginate_queryset(qs)
        if page is not None:
            ser = self.get_serializer(page, many=True)
            return self.get_paginated_response(ser.data)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, url_path=r"by-age/(?P<age>\d+)")
    def by_age(self, request, age=None):
        age = int(age)
        qs = self.queryset.filter(
            module__age_group__min_age__lte=age
        ).filter(
            Q(module__age_group__max_age__isnull=True) |
            Q(module__age_group__max_age__gte=age)
        )
        page = self.paginate_queryset(qs)
        if page is not None:
            ser = self.get_serializer(page, many=True)
            return self.get_paginated_response(ser.data)
        return Response(self.get_serializer(qs, many=True).data)



# class MyPlanView(APIView):
#     """
#     GET /api/my-nutrition-plan              → both sections (default)
#     GET /api/my-nutrition-plan?type=nutrition  → nutrition only
#     GET /api/my-nutrition-plan?type=lifestyle  → lifestyle only
#     """
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         # ── 0. which section(s) does the caller want? ──────────────
#         type_q = request.query_params.get("type", "").lower()
#         if type_q not in ("", "nutrition", "lifestyle"):
#             return Response({"detail": "type must be nutrition or lifestyle"},
#                             status=status.HTTP_400_BAD_REQUEST)

#         # ── 1. get age ─────────────────────────────────────────────
#         try:
#             age = get_user_age(request.user)
#         except Exception as exc:
#             return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

#         # ── 2. fetch applicable modules ────────────────────────────
#         modules = (
#             Module.objects
#             .select_related("age_group")
#             .prefetch_related("module_foods__food", "module_activities__activity")
#             .filter(age_group__min_age__lte=age)
#             .filter(Q(age_group__max_age__isnull=True) |
#                     Q(age_group__max_age__gte=age))
#         )
#         if type_q == "nutrition":
#             modules = modules.filter(type=Module.NUTRITION)
#         elif type_q == "lifestyle":
#             modules = modules.filter(type=Module.LIFESTYLE)

#         # ── 3. serialize the modules ───────────────────────────────
#         serialized = ModulePlanSerializer(
#             modules, many=True, context={"request": request}
#         ).data

#         # ── 4. separate into nutrition/lifestyle ───────────────────
#         nutrition, lifestyle = [], []
#         for m in serialized:
#             bundle = {"module_id": m["id"], "module": m["name"]}
#             if m["type"] == "NUT":
#                 bundle["foods"] = m["foods"]
#                 nutrition.append(bundle)
#             else:
#                 bundle["habits"] = m["habits"]
#                 lifestyle.append(bundle)

#         # ── 5. get today’s nutrition logs ──────────────────────────
#         today = date.today()
#         today_entries = NutraEntry.objects.filter(
#             session__user=request.user,
#             session__date=today,
#             food__isnull=False  # Only nutrition entries
#         ).select_related('food')

#         total_today_score = today_entries.aggregate(total=Sum('score'))['total'] or 0
#         today_log = NutraEntryReadSerializer(today_entries, many=True).data

#         cleaned_log = [
#             {
#                 "name": entry["item"]["name"],
#                 "score": entry["score"],
#                 "short_name": entry["item"].get("short_name", entry["item"]["short_name"])
#             }
#             for entry in today_log
#         ]

#         # ── 6. prepare final payload ───────────────────────────────
#         payload = {
#             "age": age,
#             "today_total_nutrition_score": total_today_score,
#             "today_logged_nutrition": cleaned_log,
#         }
#         if type_q in ("", "nutrition"):
#             payload["nutrition"] = nutrition
#         if type_q in ("", "lifestyle"):
#             payload["lifestyle"] = lifestyle

#         return Response(payload)


class MyPlanView(APIView):
    """
    GET /api/my-nutrition-plan
    GET /api/my-nutrition-plan?type=nutrition
    GET /api/my-nutrition-plan?type=lifestyle
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # ── 0. Which section(s)? ─────────────────────────────────────────────
        type_q = request.query_params.get("type", "").lower()
        if type_q not in ("", "nutrition", "lifestyle"):
            return Response(
                {"detail": "type must be nutrition or lifestyle"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── 1. Detect user age ─────────────────────────────────────────────────
        try:
            age = get_user_age(request.user)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # ── 2. Fetch modules for the user's age group ─────────────────────────
        modules = (
            Module.objects
            .select_related("age_group")
            .prefetch_related(
                "module_foods__food",
                "module_activities__activity",
                # NEW: fetch media files (audio/video)
                "module_activities"
            )
            .filter(age_group__min_age__lte=age)
            .filter(
                Q(age_group__max_age__isnull=True) |
                Q(age_group__max_age__gte=age)
            )
        )

        # Spec-correct module visibility:
        # - Teens: show teen nutrition modules (not adult Disc/Muscle split modules).
        # - Adults: show Disc/Muscle nutrition modules (not teen-only boosting lists).
        if age < 21:
            # Exclude adult-only nutrition buckets for teens.
            adult_cats = ["disc", "muscle"]
            modules = modules.exclude(
                type=Module.NUTRITION,
                nutrition_category__in=adult_cats,
            )
        else:
            # Adults: exclude teen-only nutrition modules.
            modules = modules.exclude(
                type=Module.NUTRITION,
                nutrition_category="teen",
            )

        if type_q == "nutrition":
            modules = modules.filter(type=Module.NUTRITION)
        elif type_q == "lifestyle":
            modules = modules.filter(type=Module.LIFESTYLE)

        # ── 3. Serialize modules (this includes audio/video automatically) ────
        serialized = ModulePlanSerializer(
            modules, many=True, context={"request": request}
        ).data

        # ── 4. Split into nutrition / lifestyle blocks ────────────────────────
        nutrition = []
        lifestyle = []
        for m in serialized:
            bundle = {
                "module_id": m["id"],
                "module": m["name"],
                "short_name": m["short_name"],
                "action_btn": m["action_btn"],
                "background_image": m["background_image"],
                "icon_image": m["icon_image"],
                "tag_line": m["tag_line"],
            }
            if m["type"] == "NUT":
                bundle["foods"] = m["foods"]
                nutrition.append(bundle)
            else:
                habits = m.get("habits", [])

                highest_score = 0
                completed_score = 0

                if habits:
                    highest_score = max(h.get("score", 0) for h in habits)

                    completed_scores = [
                        h.get("score", 0)
                        for h in habits
                        if h.get("completed") is True
                    ]
                    if completed_scores:
                        completed_score = max(completed_scores)

                # ✅ ADD HERE (after action_btn)
                bundle["highest_score"] = highest_score
                bundle["completed_score"] = completed_score

                bundle["habits"] = habits
                lifestyle.append(bundle)

        # ── 5. Fetch today's nutrition logs ───────────────────────────────────
        today = date.today()
        today_entries = (
            NutraEntry.objects
            .filter(
                session__user=request.user,
                session__date=today,
                food__isnull=False      # only nutrition logs
            )
            .select_related("food")
        )

        total_today_score = today_entries.aggregate(total=Sum("score"))["total"] or 0

        today_log = NutraEntryReadSerializer(today_entries, many=True).data

        cleaned_log = [
            {
                "name": entry["item"]["name"],
                "score": entry["score"],
                "short_name": entry["item"].get(
                    "short_name", entry["item"]["short_name"]
                )
            }
            for entry in today_log
        ]

        # ── 6. Final response ─────────────────────────────────────────────────
        payload = {
            "age": age,
            "today_total_nutrition_score": total_today_score,
            "today_logged_nutrition": cleaned_log,
        }

        if type_q in ("", "nutrition"):
            payload["nutrition"] = nutrition

        if type_q in ("", "lifestyle"):
            payload["lifestyle"] = lifestyle  # ← audio/video included here

        return Response(payload)