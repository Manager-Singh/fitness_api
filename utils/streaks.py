from datetime import timedelta
from nutration.models_log import NutraSession, NutraEntry
from workouts.models import WorkoutSession, WorkoutEntry, Tier, RoutineType
from utils.age import get_user_age
from utils.user_time import user_today


def _adult_food_requirement_met(user, day):
    # Part 2 — adult nutrition redesign: requirement is met when the day has both protein
    # AND hydration logged (the protein+hydration model replaces the old disc/muscle foods).
    from utils.adult_nutrition import (
        adult_hydration_points,
        adult_protein_points,
        get_adult_nutrition_day,
    )

    row = get_adult_nutrition_day(user, day)
    if not row:
        return False
    return (
        adult_protein_points(row.protein_grams) > 0
        and adult_hydration_points(row.water_ml, row.spine_500ml_count) > 0
    )


def _teen_food_requirement_met(user, day):
    return NutraEntry.objects.filter(
        session__user=user,
        session__date=day,
        food__isnull=False,
    ).exists()


def _core_exercises_done(user, day, routine_type):
    """
    Spec-aligned: core assignment should come from the active routine itself, not
    from whether a WorkoutSession row exists for the day.

    A day counts as "core complete" when the user has completed every CORE exercise
    assigned in their active routine for that routine_type on that calendar day.
    """
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

    # Preferred: rows linked to user_routine_exercise (newer data path).
    completed_exercise_ids = set(
        WorkoutEntry.objects.filter(
            session__user=user,
            session__date=day,
            session__user_routine__routine_type=routine_type,
            user_routine_exercise__tier=Tier.CORE,
        ).values_list("exercise_id", flat=True)
    )

    # Fallback: older rows may have user_routine_exercise=NULL; count by exercise_id.
    if not assigned_core_exercise_ids.issubset(completed_exercise_ids):
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

    # Unified teen POSTURE routine: Core 6 includes Jump Rope + Bodyweight Squats.
    return (
        _core_exercises_done(user, day, RoutineType.POSTURE)
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

    # Must match workout/nutrition log_date semantics (user timezone), not server local midnight.
    today = user_today(user)

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
