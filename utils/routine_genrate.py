
# # workouts/utils/routine_utils.py

from django.db import transaction
from django.db.models import Count, Q
from django.core.exceptions import ValidationError
from workouts.models import (
    UserRoutine, UserRoutineExercise,
    VariantExercise, RoutineVariant, AgeBracket,
    Tier, Type, Track, Exercise
)
from utils.age import get_user_age

# ----------------- AGE BASED PROGRAM CONFIG -----------------
AGE_BASED_PROGRAM_TYPES = [
    (13, 17, {
        "POSTURE": {"core": 4, "rec": 2, "beast": 2},
        "HGH": {"core": 2, "rec": 0, "beast": 1},
    }),
    (18, 20, {
        "POSTURE": {"core": 6, "rec": 2, "beast": 2},
        "HGH": {"core": 2, "rec": 0, "beast": 1},
    }),
    (21, None, {  # None = no upper limit
        "POSTURE": {"core": 6, "rec": 2, "beast": 2},
        # HGH excluded for > 20 years
    }),
]

# ----------------- HELPER FUNCTIONS -----------------
def _get_program_config(age):
    """Return program counts for the given age."""
    for min_age, max_age, config in AGE_BASED_PROGRAM_TYPES:
        if age >= min_age and (max_age is None or age <= max_age):
            return config
    raise ValidationError(f"No program config for age {age}")

def _get_exercises_by_need(variant, tier, need_type, count):
    """Get exercises for a specific tier & need type, fallback if not enough."""
    filtered = list(
        VariantExercise.objects.filter(
            variant=variant, tier=tier, type=need_type
        ).order_by("order")[:count]
    )

    if len(filtered) < count:
        exclude_ids = [ex.id for ex in filtered]
        remaining = count - len(filtered)
        fallback = VariantExercise.objects.filter(
            variant=variant, tier=tier
        ).exclude(id__in=exclude_ids).order_by("order")[:remaining]
        filtered.extend(fallback)

    return filtered

def _get_valid_variant(age, routine_type):
    """Return RoutineVariant for given age & type, preferring more core exercises."""
    track_map = {
        "POSTURE": [Track.ESSENTIALS, Track.POSTURE],
        "HGH": [Track.HGH],
    }

    age_bracket = AgeBracket.objects.filter(
        min_age__lte=age
    ).filter(
        Q(max_age__gte=age) | Q(max_age__isnull=True)
    ).first()

    if not age_bracket:
        raise ValidationError("No suitable age bracket found")

    variants = (
        RoutineVariant.objects
        .filter(age_bracket=age_bracket, track__in=track_map[routine_type])
        .annotate(
            core_ex_count=Count(
                "prescriptions",
                filter=Q(prescriptions__tier=Tier.CORE)
            )
        )
        .order_by("template__name", "-core_ex_count")
    )

    if not variants.exists():
        raise ValidationError(f"No routine variant found for {routine_type}")

    return variants.first()

# ----------------- MAIN UTILITY -----------------
@transaction.atomic
def generate_user_routines(user, optimization_breakdown):
    """Generate personalized routines for a user based on age & optimization needs."""
    age = get_user_age(user)
    if age is None:
        raise ValidationError("User age not found.")

    program_config = _get_program_config(age)

    # Deactivate existing active routines
    UserRoutine.objects.filter(user=user, is_active=True).update(is_active=False)

    created_routines = []

    # Sort needs by lowest optimization %
    needs_sorted = sorted(
        optimization_breakdown.items(),
        key=lambda kv: kv[1].get("percent_optimized", 100)
    )

    for routine_type, counts in program_config.items():
        variant = _get_valid_variant(age, routine_type)
        selected = []

        # CORE exercises
        core_exercises = list(
            VariantExercise.objects.filter(
                variant=variant, tier=Tier.CORE
            ).order_by("order")[:counts["core"]]
        )
        selected.extend(core_exercises)

        # RECOMMENDED exercises
        if counts["rec"] > 0 and needs_sorted:
            primary_need = needs_sorted[0][0]
            selected.extend(
                _get_exercises_by_need(variant, Tier.RECOMMENDED, primary_need, counts["rec"])
            )

        # BEAST exercises
        if counts["beast"] > 0 and needs_sorted:
            secondary_need = needs_sorted[1][0] if len(needs_sorted) > 1 else needs_sorted[0][0]
            selected.extend(
                _get_exercises_by_need(variant, Tier.BEAST, secondary_need, counts["beast"])
            )

        # Deduplicate exercises
        unique_exercises = []
        seen_ex_ids = set()
        for ve in selected:
            if ve.exercise_id not in seen_ex_ids:
                unique_exercises.append(ve)
                seen_ex_ids.add(ve.exercise_id)

        if not unique_exercises:
            continue

        # Create UserRoutine
        routine = UserRoutine.objects.create(
            user=user,
            routine_type=routine_type,
            is_active=True,
            scan_score=optimization_breakdown,
            optimization_breakdown=optimization_breakdown,
        )

        # Add exercises to UserRoutine
        for idx, variant_ex in enumerate(unique_exercises, start=1):
            # UserRoutineExercise.objects.create(
            #     routine=routine,
            #     exercise=variant_ex.exercise,
            #     tier=variant_ex.tier,
            #     order=idx,
            #     sets=variant_ex.sets,
            #     qty_min=variant_ex.quantity_min,
            #     qty_max=variant_ex.quantity_max,
            #     unit=variant_ex.unit,
            #     notes=f"{variant_ex.tier.upper()} - {variant_ex.get_type_display()}",
            # )
            UserRoutineExercise.objects.create(
                routine=routine,
                variant_exercise=variant_ex,   # ✅ STORE SOURCE
                exercise=variant_ex.exercise,
                tier=variant_ex.tier,
                order=idx,
                sets=variant_ex.sets,
                qty_min=variant_ex.quantity_min,
                qty_max=variant_ex.quantity_max,
                unit=variant_ex.unit,
                notes=f"{variant_ex.tier.upper()} - {variant_ex.get_type_display()}",
            )

        created_routines.append(routine)

    return created_routines