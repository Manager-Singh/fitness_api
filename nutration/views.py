from django.db.models import Q, Sum
from rest_framework import viewsets,status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from utils.age import get_user_age, get_user_age_exact
from utils.check_payment import check_subscription_or_response
from utils.paywall_flags import effective_is_paid

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
from utils.teen_nutrition_cap import TEEN_CAP_MESSAGE_EXACT
from utils.user_time import user_today
from nutration.food_macros import food_macros_from_entries, hydration_summary_for_user
from utils.adult_nutrition import is_adult_flat_food_user
from utils.nutrition_plan import account_age_bounds_payload, module_filter_age, modules_for_user_age_q
from utils.paywall_flags import account_age_bounds



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
            age_exact = get_user_age_exact(request.user)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Unified adult detection across nutrition APIs: respects an explicit
        # account_tier override and otherwise falls back to the sex-specific adult
        # age band (female 18+, male 21+). Same helper used for hydration + scoring.
        adult_nutrition_plan = is_adult_flat_food_user(request.user, age)
        subscription_data = check_subscription_or_response(request.user).data
        adult_paid_lifestyle = bool(
            adult_nutrition_plan
            and effective_is_paid(request.user, subscription_data, age_exact=age_exact)
        )

        # ── 2. Fetch modules for the user's age group (sex-specific adult band) ─
        plan_age = module_filter_age(request.user, age, age_exact=age_exact)
        modules = (
            Module.objects
            .select_related("age_group")
            .prefetch_related(
                "module_foods__food",
                "module_activities__activity",
                # NEW: fetch media files (audio/video)
                "module_activities"
            )
            .filter(modules_for_user_age_q(request.user, age, age_exact=age_exact))
            .order_by("age_group__min_age", "type", "sort_order", "name")
        )

        # Spec-correct module visibility (sex-specific adult band: female 18+, male 21+):
        # - Teens: teen nutrition modules only.
        # - Adults: Disc/Muscle adult plan modules (not teen GrowthMax lists).
        if not adult_nutrition_plan:
            # Exclude adult-only nutrition buckets for teens.
            adult_cats = ["disc", "muscle"]
            teen_max = int(account_age_bounds(user=request.user)["teen_max"])
            modules = modules.exclude(
                type=Module.NUTRITION,
                nutrition_category__in=adult_cats,
            ).exclude(
                age_group__min_age__gt=teen_max,
            )
        else:
            from utils.adult_nutrition import adult_nutrition_plan_module_q

            # Adults: exclude teen-only nutrition modules.
            modules = modules.exclude(
                type=Module.NUTRITION,
                nutrition_category="teen",
            ).exclude(
                type=Module.NUTRITION,
                name__icontains="growthmax",
            )
            if type_q in ("", "nutrition", "lifestyle"):
                from utils.adult_nutrition import adult_lifestyle_plan_module_pks

                # Adult disc/muscle may live in 21+ age groups while female adults start at 18.
                # Paid adults (both sexes) get the full lifestyle catalog (often teen age band only).
                age_filtered_pks = set(modules.values_list("pk", flat=True))
                adult_nut_pks = set(
                    Module.objects.filter(adult_nutrition_plan_module_q()).values_list("pk", flat=True)
                )
                adult_life_pks = (
                    adult_lifestyle_plan_module_pks() if adult_paid_lifestyle else set()
                )
                modules = (
                    Module.objects.select_related("age_group")
                    .prefetch_related(
                        "module_foods__food",
                        "module_activities__activity",
                        "module_activities",
                    )
                    .filter(pk__in=age_filtered_pks | adult_nut_pks | adult_life_pks)
                    .order_by("age_group__min_age", "type", "sort_order", "name")
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
                "wheel_type": bool(m.get("wheel_type")),
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

        # ── 5. Fetch today's nutrition logs (same rules as nutra-logs POST) ──
        log_date = user_today(request.user)
        today_entries = (
            NutraEntry.objects
            .filter(
                session__user=request.user,
                session__date=log_date,
                food__isnull=False      # only nutrition logs
            )
            .select_related("food", "module")
        )

        raw_today_food_points = float(today_entries.aggregate(total=Sum("score"))["total"] or 0)
        # Traceable caps — must match nutration/views_log.py (adult flat model, teen 35).
        if not adult_nutrition_plan:
            cap_limit = 35.0
            traceable_today_food_points = min(raw_today_food_points, cap_limit)
            cap_reached = bool(raw_today_food_points >= cap_limit)
            diary_note = TEEN_CAP_MESSAGE_EXACT if cap_reached else None
        else:
            from workouts.set_progress import credited_points_for_day
            from utils.adult_nutrition import (
                ADULT_NUTRITION_POINTS_CAP,
                adult_nutrition_points_today,
            )

            # Part 2 adult nutrition = protein + hydration points from
            # AdultNutritionDay (server-authoritative), gated by posture work so
            # this matches users/spec_runtime.py and /api/adult-nutrition exactly.
            posture_pts = float(credited_points_for_day(request.user, log_date, routine_type="posture"))
            adult_points = int(adult_nutrition_points_today(request.user, log_date))
            traceable_today_food_points = float(adult_points if posture_pts > 0 else 0.0)
            cap_limit = float(ADULT_NUTRITION_POINTS_CAP)
            cap_reached = bool(adult_points >= int(ADULT_NUTRITION_POINTS_CAP))
            diary_note = (
                f"You've reached today's nutrition cap ({int(cap_limit)} pts)."
            ) if cap_reached else None

        today_log = NutraEntryReadSerializer(today_entries, many=True).data

        macro_totals = food_macros_from_entries(today_entries)
        hydration_today = hydration_summary_for_user(
            request.user,
            log_date,
            adult_nutrition_plan=adult_nutrition_plan,
        )

        cleaned_log = [
            {
                "name": entry["item"]["name"],
                "score": entry["score"],
                "short_name": entry["item"].get(
                    "short_name", entry["item"]["short_name"]
                ),
                "calories": entry["item"].get("calories"),
                "protein": entry["item"].get("protein"),
            }
            for entry in today_log
            if entry["item"].get("type") == "food"
        ]

        # ── 6. Final response ─────────────────────────────────────────────────
        payload = {
            **account_age_bounds_payload(request.user, age, age_exact=age_exact),
            "plan_age": plan_age,
            "log_date": str(log_date),
            # Same semantics as POST /api/nutra-logs: traceable food points (capped).
            "daily_nutrition_pts_today": int(round(traceable_today_food_points)),
            "today_total_nutrition_score": float(traceable_today_food_points),
            "today_total_nutrition_score_raw": float(raw_today_food_points),
            "today_total_food_score_traceable": float(traceable_today_food_points),
            "today_total_food_score_raw": float(raw_today_food_points),
            "today_total_calories": macro_totals["today_total_calories"],
            "today_total_protein": macro_totals["today_total_protein"],
            "hydration_today": hydration_today,
            "cap_reached": cap_reached,
            "cap_limit": cap_limit,
            "diary_note": diary_note,
            "today_logged_nutrition": cleaned_log,
        }

        if type_q in ("", "nutrition"):
            payload["nutrition"] = nutrition

        if type_q in ("", "lifestyle"):
            payload["lifestyle"] = lifestyle  # ← audio/video included here
            from habits.services import build_habits_plan_payload

            payload["habits"] = build_habits_plan_payload(request.user, log_date)

        return Response(payload)