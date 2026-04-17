from users.models import DailyLog
from django.apps import apps
from django.db.models import Q, Sum

WorkoutEntry = apps.get_model("workouts", "WorkoutEntry")
NutraEntry = apps.get_model("nutration", "NutraEntry")


def apply_engine_routing(user, log_date, age_exact, points=0, routine_type=None, entry_kind="exercise"):
    """
    Canonical Section-11 routing for daily engine buckets.
    entry_kind: exercise | food | lifestyle
    routine_type: posture | hgh (for exercise entries)
    """
    daily, _ = DailyLog.objects.get_or_create(user=user, log_date=log_date)
    pts = max(0, int(points or 0))

    if entry_kind == "exercise":
        if str(routine_type or "").lower() == "hgh" and age_exact < 21:
            daily.engine2_points += pts
        else:
            daily.engine1_points += pts
        daily.exercise_points += pts
    elif entry_kind == "food":
        daily.food_points += pts
        if age_exact >= 21:
            daily.engine1_points += pts
        else:
            daily.engine2_points += pts
    elif entry_kind == "lifestyle":
        daily.lifestyle_points += pts
        if age_exact < 21:
            daily.engine2_points += pts
        else:
            daily.diary_only_points += pts

    # Caps
    if age_exact >= 21:
        daily.food_points = min(max(0, int(daily.food_points)), 12)
        daily.engine1_points = max(0, int(daily.engine1_points))
    else:
        # Section-11 teen per-channel caps (write-time recompute):
        # hgh + food(35) + sleep(10) + sunlight(6) + meditation(2) + hydration(1)
        raw_hgh_points = WorkoutEntry.objects.filter(
            session__user=user,
            session__date=log_date,
            session__user_routine__routine_type__iexact="hgh",
        ).aggregate(total=Sum("points"))["total"] or 0

        life_qs = NutraEntry.objects.filter(
            session__user=user,
            session__date=log_date,
        ).select_related("module")

        def _sum_module_contains(keyword):
            return life_qs.filter(module__name__icontains=keyword).aggregate(total=Sum("score"))["total"] or 0

        food_points = life_qs.filter(food__isnull=False).aggregate(total=Sum("score"))["total"] or 0

        sleep_points = _sum_module_contains("sleep")
        sunlight_points = _sum_module_contains("sun")
        meditation_points = _sum_module_contains("meditat")
        hydration_points = (
            life_qs.filter(Q(module__name__icontains="hydrat") | Q(module__name__icontains="water"))
            .aggregate(total=Sum("score"))["total"] or 0
        )

        # Exact teen per-channel caps from spec.
        hgh_points = min(raw_hgh_points, 30)
        daily.engine2_points = int(
            hgh_points
            + min(food_points, 35)
            + min(sleep_points, 10)
            + min(sunlight_points, 6)
            + min(meditation_points, 2)
            + min(hydration_points, 1)
        )
        daily.engine2_points = max(0, int(daily.engine2_points))

    daily.save()
    return daily
