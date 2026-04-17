from datetime import timedelta
from django.utils import timezone
from nutration.models_log import NutraSession, NutraEntry
from workouts.models import WorkoutSession, WorkoutEntry, Tier, RoutineType
from utils.age import get_user_age


def _adult_food_requirement_met(user, day):
    foods = NutraEntry.objects.filter(
        session__user=user,
        session__date=day,
        food__isnull=False,
    ).select_related("module")

    has_disc_or_spine = False
    has_muscle_or_repair = False

    for entry in foods:
        module_name = ((entry.module.name if entry.module else "") or "").lower()
        if any(token in module_name for token in ("disc", "lubric", "spine")):
            has_disc_or_spine = True
        if any(token in module_name for token in ("muscle", "repair", "fuel")):
            has_muscle_or_repair = True

    return has_disc_or_spine and has_muscle_or_repair


def _teen_food_requirement_met(user, day):
    return NutraEntry.objects.filter(
        session__user=user,
        session__date=day,
        food__isnull=False,
    ).exists()


def _core_exercises_done(user, day, routine_type):
    completed_core_ids = set(
        WorkoutEntry.objects.filter(
            session__user=user,
            session__date=day,
            session__user_routine__routine_type=routine_type,
            user_routine_exercise__tier=Tier.CORE,
        ).values_list("user_routine_exercise_id", flat=True)
    )

    assigned_core_ids = set(
        WorkoutSession.objects.filter(
            user=user,
            date=day,
            user_routine__routine_type=routine_type,
            user_routine__is_active=True,
            user_routine__exercises__tier=Tier.CORE,
        ).values_list("user_routine__exercises__id", flat=True)
    )

    if not assigned_core_ids:
        return False
    if assigned_core_ids.issubset(completed_core_ids):
        return True

    # Fallback: older WorkoutEntry rows may have user_routine_exercise=NULL.
    # Count completion by intersecting exercise_id against assigned core exercises.
    from workouts.models import UserRoutineExercise

    assigned_core_exercise_ids = set(
        UserRoutineExercise.objects.filter(
            routine__user=user,
            routine__is_active=True,
            routine__routine_type=routine_type,
            tier=Tier.CORE,
        ).values_list("exercise_id", flat=True)
    )
    if not assigned_core_exercise_ids:
        return False

    completed_exercise_ids = set(
        WorkoutEntry.objects.filter(
            session__user=user,
            session__date=day,
            session__user_routine__routine_type=routine_type,
        )
        .values_list("exercise_id", flat=True)
        .distinct()
    )
    return assigned_core_exercise_ids.issubset(completed_exercise_ids)


def _is_valid_streak_day(user, day, age):
    if age >= 21:
        return _core_exercises_done(user, day, RoutineType.POSTURE) and _adult_food_requirement_met(user, day)

    return (
        _core_exercises_done(user, day, RoutineType.POSTURE)
        and _core_exercises_done(user, day, RoutineType.HGH)
        and _teen_food_requirement_met(user, day)
    )


def _current_validated_streak(user, today, age):
    streak = 0
    day = today
    while _is_valid_streak_day(user, day, age):
        streak += 1
        day -= timedelta(days=1)
    return streak


def get_user_streaks(user,subscription_data):
    """
    Returns all streak-related data in one call.
    """

    today = timezone.localdate()

    nutra_set = set(
        NutraSession.objects
        .filter(user=user)
        .values_list("date", flat=True)
        .distinct()
    )
    workout_set = set(
        WorkoutSession.objects
        .filter(user=user)
        .values_list("date", flat=True)
        .distinct()
    )

    try:
        age = get_user_age(user)
    except Exception:
        age = 0

    nutrition_streak = 0
    day = today
    while day in nutra_set:
        nutrition_streak += 1
        day -= timedelta(days=1)

    workout_streak = 0
    day = today
    while day in workout_set:
        workout_streak += 1
        day -= timedelta(days=1)

    health_streak = _current_validated_streak(user, today, age)

    # ─────────────────────────────────────────────
    # Final payload
    # ─────────────────────────────────────────────

    from .leaderboard import get_user_leaderboard_rank
    leaderboard_data = get_user_leaderboard_rank(
        user,
        subscription_data,
        routine_type=None   # or "POSTURE" / "HGH" if needed
    )
    return {
        "nutrition": {
            "today": today in nutra_set,
            "current_streak": nutrition_streak,
            # "longest_streak": longest_streak(nutra_dates),
        },
        "workout": {
            "today": today in workout_set,
            "current_streak": workout_streak,
            # "longest_streak": longest_streak(workout_dates),
        },
        "health": {
            "current_streak": health_streak,
        },
        "leaderboard": leaderboard_data,
    }
