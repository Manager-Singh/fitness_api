"""Helpers for durable per-set workout progress and crediting."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

POINT_DECIMAL_PLACES = Decimal("0.0001")


@dataclass(frozen=True)
class CreditedWorkoutUnit:
    exercise: object
    routine_type: str
    points: Decimal
    user_routine_exercise_id: int | None = None


def decimal_points(value) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(POINT_DECIMAL_PLACES, rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.0000")


def expected_sets_for_assignment(user_routine_exercise=None, *, exercise=None, entry=None) -> int:
    """Return the authoritative set count for an assigned exercise."""
    ve = getattr(user_routine_exercise, "variant_exercise", None)
    for value in (
        getattr(ve, "sets", None),
        getattr(user_routine_exercise, "sets", None),
        getattr(entry, "sets_done", None),
    ):
        try:
            value = int(value or 0)
        except Exception:
            value = 0
        if value > 0:
            return value
    return 1


def per_set_points(exercise, total_sets: int) -> Decimal:
    total_sets = max(1, int(total_sets or 1))
    points = Decimal(str(getattr(exercise, "points", 0) or 0))
    return (points / Decimal(total_sets)).quantize(POINT_DECIMAL_PLACES, rounding=ROUND_HALF_UP)


def set_completion_queryset(user, log_date, *, user_routine_exercise=None, exercise=None):
    from workouts.models import WorkoutSetCompletion

    qs = WorkoutSetCompletion.objects.filter(user=user, log_date=log_date)
    if user_routine_exercise is not None:
        qs = qs.filter(user_routine_exercise=user_routine_exercise)
    elif exercise is not None:
        qs = qs.filter(exercise=exercise)
    return qs


def completed_set_count(user, log_date, *, user_routine_exercise=None, exercise=None) -> int:
    return int(
        set_completion_queryset(
            user,
            log_date,
            user_routine_exercise=user_routine_exercise,
            exercise=exercise,
        )
        .values("set_index")
        .distinct()
        .count()
    )


def progress_for_assignment(user, log_date, user_routine_exercise) -> dict:
    from workouts.models import WorkoutEntry

    total_sets = expected_sets_for_assignment(user_routine_exercise)
    done = completed_set_count(
        user,
        log_date,
        user_routine_exercise=user_routine_exercise,
        exercise=getattr(user_routine_exercise, "exercise", None),
    )
    if done == 0 and WorkoutEntry.objects.filter(
        session__user=user,
        session__date=log_date,
        user_routine_exercise=user_routine_exercise,
    ).exists():
        done = total_sets
    done = min(done, total_sets)
    return {
        "completed_sets": done,
        "total_sets": total_sets,
        "progress_fraction": float(Decimal(done) / Decimal(total_sets)) if total_sets else 0.0,
        "partially_completed": bool(0 < done < total_sets),
        "completed": bool(total_sets > 0 and done >= total_sets),
    }


def fully_completed_assignment_ids(user, log_date, *, routine_type=None):
    from workouts.models import UserRoutineExercise

    qs = UserRoutineExercise.objects.filter(routine__user=user, routine__is_active=True)
    if routine_type:
        qs = qs.filter(routine__routine_type=routine_type)

    completed = set()
    for ure in qs.select_related("variant_exercise", "exercise"):
        progress = progress_for_assignment(user, log_date, ure)
        if progress["completed"]:
            completed.add(ure.id)
    return completed


def count_fully_completed_assignments(user, log_date, *, routine_type=None) -> int:
    return len(fully_completed_assignment_ids(user, log_date, routine_type=routine_type))


def iter_credited_workout_units(user, log_date):
    """Yield credited set units, with legacy full-entry fallback for rows not yet set-backed."""
    from workouts.models import WorkoutEntry, WorkoutSetCompletion

    completed_entry_ids = set()
    completions = (
        WorkoutSetCompletion.objects.filter(user=user, log_date=log_date)
        .select_related("exercise", "session__user_routine", "workout_entry__session__user_routine")
        .order_by("id")
    )
    for completion in completions:
        if completion.workout_entry_id:
            completed_entry_ids.add(completion.workout_entry_id)
        session = completion.session or getattr(completion.workout_entry, "session", None)
        routine = getattr(session, "user_routine", None)
        yield CreditedWorkoutUnit(
            exercise=completion.exercise,
            routine_type=str(getattr(routine, "routine_type", "") or "").lower(),
            points=decimal_points(completion.points_credited),
            user_routine_exercise_id=completion.user_routine_exercise_id,
        )

    fallback_qs = WorkoutEntry.objects.filter(session__user=user, session__date=log_date).select_related(
        "exercise",
        "session__user_routine",
        "user_routine_exercise",
    )
    if completed_entry_ids:
        fallback_qs = fallback_qs.exclude(id__in=completed_entry_ids)
    for entry in fallback_qs:
        routine = getattr(getattr(entry, "session", None), "user_routine", None)
        yield CreditedWorkoutUnit(
            exercise=getattr(entry, "exercise", None),
            routine_type=str(getattr(routine, "routine_type", "") or "").lower(),
            points=decimal_points(getattr(entry, "points", 0)),
            user_routine_exercise_id=getattr(entry, "user_routine_exercise_id", None),
        )


def credited_points_for_day(user, log_date, *, routine_type=None) -> Decimal:
    total = Decimal("0.0000")
    for unit in iter_credited_workout_units(user, log_date):
        if routine_type and unit.routine_type != str(routine_type).lower():
            continue
        total += decimal_points(unit.points)
    return total.quantize(POINT_DECIMAL_PLACES, rounding=ROUND_HALF_UP)


def workout_activity_exists(user, log_date) -> bool:
    from workouts.models import WorkoutEntry, WorkoutSetCompletion

    return WorkoutSetCompletion.objects.filter(user=user, log_date=log_date).exists() or WorkoutEntry.objects.filter(
        session__user=user,
        session__date=log_date,
    ).exists()
