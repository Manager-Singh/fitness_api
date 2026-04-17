
# # workouts/utils/routine_utils.py

from django.db import transaction
from django.db.models import Count, Q
from django.core.exceptions import ValidationError
from workouts.models import (
    UserRoutine, UserRoutineExercise,
    VariantExercise, RoutineVariant, AgeBracket,
    Tier, Type, Track, Exercise, ExerciseCategory
)
from utils.age import get_user_age
from posture_questions.models import PostureQuestion

# ----------------- AGE BASED PROGRAM CONFIG -----------------
AGE_BASED_PROGRAM_TYPES = [
    (13, 17, {
        "POSTURE": {"core": 4, "rec": 1, "beast": 1},
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

SECTION10_NEED_PRIORITY = [
    "spinal_compression",
    "posture_collapse",
    "pelvic_tilt_back",
    "leg_hamstring",
]

SEGMENT_TO_EXERCISE_TYPE = {
    "spinal_compression": Type.SPINALCPMPRESSION,
    # DB enum is postural_collapse; keep spec key posture_collapse mapped here.
    "posture_collapse": Type.POSTURALCOLLAPSE,
    "pelvic_tilt_back": Type.PELCIVTILTBACK,
    "leg_hamstring": Type.LEGHAMSTRING,
}

# Spec guard: ensure posture routines never include HGH/Environment exercises and vice versa.
POSTURE_ALLOWED_CATEGORIES = {
    ExerciseCategory.POSTURE,
    ExerciseCategory.GENERAL,
}
HGH_ALLOWED_CATEGORIES = {
    ExerciseCategory.HGH,
    ExerciseCategory.ENVIRONMENT,
    ExerciseCategory.GENERAL,
}


def _variant_qs(variant, tier, mapped_need=None, allowed_categories=None):
    qs = VariantExercise.objects.filter(variant=variant, tier=tier)
    if mapped_need is not None:
        qs = qs.filter(type=mapped_need)
    if allowed_categories:
        qs = qs.filter(exercise__category__in=list(allowed_categories))
    return qs

# ----------------- HELPER FUNCTIONS -----------------
def _get_program_config(age):
    """Return program counts for the given age."""
    for min_age, max_age, config in AGE_BASED_PROGRAM_TYPES:
        if age >= min_age and (max_age is None or age <= max_age):
            return config
    raise ValidationError(f"No program config for age {age}")

def _pick_exercises_for_tier_across_ranked(
    variant, tier, needs_sorted, total_needed, exclude_exercise_ids=None
):
    """
    Section 10.3 / 10.5: fill Beast/Recommended slots by walking ranked segments
    (worst first), taking at most one new exercise per segment pass, re-looping
    until `total_needed` is met. Excludes core (and optional prior picks).
    """
    exclude_exercise_ids = set(exclude_exercise_ids or [])
    if not needs_sorted or total_needed <= 0:
        return []
    selected = []
    seen = set()
    rounds = 0
    while len(selected) < total_needed and rounds < max(8, total_needed * 4):
        rounds += 1
        progressed = False
        for seg in needs_sorted:
            if len(selected) >= total_needed:
                break
            batch = _get_exercises_by_need(variant, tier, seg, 8)
            for ve in batch:
                if ve.exercise_id in exclude_exercise_ids:
                    continue
                if ve.exercise_id in seen:
                    continue
                selected.append(ve)
                seen.add(ve.exercise_id)
                progressed = True
                break
        if not progressed:
            break
    return selected


def _get_exercises_by_need(variant, tier, need_type, count, allowed_categories=None):
    """Get exercises for a specific tier & need type, fallback if not enough."""
    mapped_need = SEGMENT_TO_EXERCISE_TYPE.get(need_type, need_type)
    filtered = list(_variant_qs(variant, tier, mapped_need=mapped_need, allowed_categories=allowed_categories).order_by("order")[:count])

    if len(filtered) < count:
        exclude_ids = [ex.id for ex in filtered]
        remaining = count - len(filtered)
        fallback = (
            _variant_qs(variant, tier, allowed_categories=allowed_categories)
            .exclude(id__in=exclude_ids)
            .order_by("order")[:remaining]
        )
        filtered.extend(fallback)

    return filtered


def _topup_variant_tier(variant, tier, picks, need, exclude_exercise_ids):
    """
    Section 10.3: if segment-ranked picks exhaust before filling Beast/Recommended
    slots, promote additional exercises from the same tier (any type) by ``order``.
    """
    exclude = set(exclude_exercise_ids or [])
    for p in picks:
        exclude.add(p.exercise_id)
    out = list(picks)
    if len(out) >= need:
        return out
    extra = list(
        VariantExercise.objects.filter(variant=variant, tier=tier)
        .exclude(exercise_id__in=list(exclude))
        .order_by("order")[: max(0, need - len(out))]
    )
    out.extend(extra)
    return out


def _sorted_needs(optimization_breakdown):
    # Section 10 deterministic ordering by lowest optimization first.
    def _sort_key(item):
        seg, payload = item
        pct = payload.get("percent_optimized", 100)
        try:
            idx = SECTION10_NEED_PRIORITY.index(seg)
        except ValueError:
            idx = len(SECTION10_NEED_PRIORITY)
        return (pct, idx, seg)

    return sorted(optimization_breakdown.items(), key=_sort_key)


def _normalize_answer(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def _choice_score(ans):
    ans = _normalize_answer(ans)
    if ans.startswith("a"):
        return 2
    if ans.startswith("b"):
        return 1
    return 0


def _parse_multiselect(ans):
    """
    Supports JSON list, comma-separated letters, or plain string.
    """
    if ans is None:
        return set()
    raw = str(ans).strip()
    selected = set()
    # crude parser compatible with legacy storage.
    for token in raw.replace("[", "").replace("]", "").replace('"', "").replace("'", "").split(","):
        t = token.strip().lower()
        if not t:
            continue
        if t and t[0] in {"a", "b", "c", "d", "e"}:
            selected.add(t[0])
    return selected


def _questionnaire_ranked_segments(user):
    """
    Section 10.1 scoring + tie-break:
    Spinal > Collapse > Pelvic > Legs.
    """
    pq = PostureQuestion.objects.filter(user=user).first()
    if not pq:
        return []

    q1 = _choice_score(pq.forward_head_posture_answer)
    q2 = _choice_score(pq.gap_between_your_lower_back_answer)
    q4 = _choice_score(pq.slouch_when_standing_or_sitting_answer)
    q5 = _choice_score(pq.feel_noticeably_shorter_end_of_day_compare_to_morning_answer)
    q7 = _choice_score(pq.flexible_in_your_hamstrings_and_hips_answer)
    q8 = _choice_score(pq.active_your_core_during_daily_task_answer)
    q3 = _parse_multiselect(pq.tightness_or_discomfort_answer)

    q3a = 1 if "a" in q3 else 0
    q3b = 1 if "b" in q3 else 0
    q3c = 1 if "c" in q3 else 0
    q3d = 1 if "d" in q3 else 0

    scores = {
        "spinal_compression": q1 + q4 + q5 + q3a,
        "posture_collapse": q1 + q4 + q3a,
        "pelvic_tilt_back": q2 + q8 + q3b + q3c,
        "leg_hamstring": q7 + q3d + q3c,
    }
    tie_order = {k: i for i, k in enumerate(SECTION10_NEED_PRIORITY)}
    ranked = sorted(scores.keys(), key=lambda s: (-scores[s], tie_order.get(s, 99)))
    return ranked


def assign_adult_exercises(variant, optimization_breakdown, ranked_segments=None):
    """
    Section 10.3 adult template:
    - Core 6
    - Beast Mode 2 (walk ranked segments worst-first; one pick per pass)
    - Recommended 2 (same pattern; skips exercises already chosen)
    """
    needs_sorted = ranked_segments or [seg for seg, _ in _sorted_needs(optimization_breakdown)]
    selected = []
    core = list(
        _variant_qs(variant, Tier.CORE, allowed_categories=POSTURE_ALLOWED_CATEGORIES).order_by("order")[:6]
    )
    selected.extend(core)
    core_ids = {ve.exercise_id for ve in core}

    if needs_sorted:
        beasts = _pick_exercises_for_tier_across_ranked(
            variant, Tier.BEAST, needs_sorted, 2, exclude_exercise_ids=core_ids
        )
        # Enforce posture-only categories for adult posture routines.
        beasts = [b for b in beasts if getattr(b.exercise, "category", None) in POSTURE_ALLOWED_CATEGORIES]
        beasts = _topup_variant_tier(
            variant,
            Tier.BEAST,
            beasts,
            2,
            core_ids,
        )
        selected.extend(beasts)
        recs = _pick_exercises_for_tier_across_ranked(
            variant,
            Tier.RECOMMENDED,
            needs_sorted,
            2,
            exclude_exercise_ids=core_ids | {ve.exercise_id for ve in beasts},
        )
        recs = [r for r in recs if getattr(r.exercise, "category", None) in POSTURE_ALLOWED_CATEGORIES]
        recs = _topup_variant_tier(
            variant,
            Tier.RECOMMENDED,
            recs,
            2,
            core_ids | {ve.exercise_id for ve in beasts},
        )
        selected.extend(recs)
    return selected


def assign_teen_posture_exercises(variant, optimization_breakdown, age, ranked_segments=None):
    """
    Section 10 teen posture assignment:
    - Ages 13-17: Core 4 + Recommended 1 + Beast 1
    - Ages 18-20: Core 6 + Recommended 2 + Beast 2
    """
    core_count = 4 if 13 <= age <= 17 else 6
    rec_count = 1 if 13 <= age <= 17 else 2
    beast_count = 1 if 13 <= age <= 17 else 2
    needs_sorted = ranked_segments or [seg for seg, _ in _sorted_needs(optimization_breakdown)]
    selected = []
    selected.extend(
        list(
            _variant_qs(variant, Tier.CORE, allowed_categories=POSTURE_ALLOWED_CATEGORIES).order_by("order")[:core_count]
        )
    )

    core_ids = {ve.exercise_id for ve in selected}
    if needs_sorted:
        beasts = _pick_exercises_for_tier_across_ranked(
            variant, Tier.BEAST, needs_sorted, beast_count, exclude_exercise_ids=core_ids
        )
        beasts = [b for b in beasts if getattr(b.exercise, "category", None) in POSTURE_ALLOWED_CATEGORIES]
        beasts = _topup_variant_tier(variant, Tier.BEAST, beasts, beast_count, core_ids)
        selected.extend(beasts)
        recs = _pick_exercises_for_tier_across_ranked(
            variant,
            Tier.RECOMMENDED,
            needs_sorted,
            rec_count,
            exclude_exercise_ids=core_ids | {ve.exercise_id for ve in beasts},
        )
        recs = [r for r in recs if getattr(r.exercise, "category", None) in POSTURE_ALLOWED_CATEGORIES]
        recs = _topup_variant_tier(
            variant,
            Tier.RECOMMENDED,
            recs,
            rec_count,
            core_ids | {ve.exercise_id for ve in beasts},
        )
        selected.extend(recs)
    return selected

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

    # Deactivate existing routines (do NOT delete).
    #
    # Rationale:
    # - `WorkoutSession.user_routine` is `on_delete=PROTECT`, so deleting routines will
    #   crash once any session exists (history must remain intact).
    # - We removed the uniqueness constraint that previously forced delete-based regen.
    #
    # Invariant enforced in code: at most one active routine per user+type.
    UserRoutine.objects.filter(user=user, is_active=True).update(is_active=False)

    created_routines = []
    ranked_segments = _questionnaire_ranked_segments(user)

    for routine_type, counts in program_config.items():
        variant = _get_valid_variant(age, routine_type)
        selected = []
        if routine_type == "POSTURE" and age >= 21:
            selected = assign_adult_exercises(variant, optimization_breakdown, ranked_segments=ranked_segments)
        elif routine_type == "POSTURE" and 13 <= age <= 20:
            selected = assign_teen_posture_exercises(
                variant,
                optimization_breakdown,
                age,
                ranked_segments=ranked_segments,
            )
        else:
            # HGH/other tracks retain explicit variant ordering.
            selected.extend(
                list(
                    _variant_qs(variant, Tier.CORE, allowed_categories=HGH_ALLOWED_CATEGORIES).order_by("order")[:counts["core"]]
                )
            )
            if counts["rec"] > 0:
                selected.extend(
                    list(
                        _variant_qs(variant, Tier.RECOMMENDED, allowed_categories=HGH_ALLOWED_CATEGORIES).order_by("order")[:counts["rec"]]
                    )
                )
            if counts["beast"] > 0:
                selected.extend(
                    list(
                        _variant_qs(variant, Tier.BEAST, allowed_categories=HGH_ALLOWED_CATEGORIES).order_by("order")[:counts["beast"]]
                    )
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