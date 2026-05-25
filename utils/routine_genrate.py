
# workouts/utils/routine_utils.py

import json
import logging

from django.db import transaction
from django.db.models import Count, Q
from django.core.exceptions import ValidationError
from workouts.models import (
    UserRoutine, UserRoutineExercise,
    VariantExercise, RoutineVariant, AgeBracket,
    Tier, Type, Track, Exercise, ExerciseCategory, RoutineType, Unit,
)
from utils.age import get_user_age
from posture_questions.models import PostureQuestion
from utils.exercise_assignment import (
    segment_losses_from_breakdown,
    ranked_segments_from_losses,
    get_age_multipliers,
    select_adult_recommended_beast,
    select_teen_recommended_beast,
    adult_scoring_pool_queryset,
    teen_scoring_pool_queryset,
)
from utils.exercise_prescriptions import prescription_for_exercise_name
from workouts.exercise_assignment_data import (
    TEEN_CORE_6_NAMES,
    normalize_exercise_name,
    spec_key_for_name,
)

logger = logging.getLogger(__name__)

# ----------------- AGE BASED PROGRAM CONFIG -----------------
AGE_BASED_PROGRAM_TYPES = [
    (13, 17, {
        "POSTURE": {"core": 6, "rec": 2, "beast": 2},
    }),
    (18, 20, {
        "POSTURE": {"core": 6, "rec": 2, "beast": 2},
    }),
    (21, None, {
        "POSTURE": {"core": 6, "rec": 2, "beast": 2},
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
    "posture_collapse": Type.POSTURALCOLLAPSE,
    "pelvic_tilt_back": Type.PELCIVTILTBACK,
    "leg_hamstring": Type.LEGHAMSTRING,
}

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


def _get_program_config(age):
    for min_age, max_age, config in AGE_BASED_PROGRAM_TYPES:
        if age >= min_age and (max_age is None or age <= max_age):
            return config
    raise ValidationError(f"No program config for age {age}")


def _sorted_needs(optimization_breakdown):
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


def _parse_options(value):
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    raw = str(value).strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(v) for v in parsed]
    except Exception:
        pass
    return [raw]


def _coerce_letter(value, options=None):
    txt = _normalize_answer(value)
    if txt and txt[0] in {"a", "b", "c", "d", "e"}:
        return txt[0]
    opts = _parse_options(options)
    if not opts:
        return ""
    norm_opts = [_normalize_answer(o) for o in opts]
    if txt in norm_opts:
        idx = norm_opts.index(txt)
    else:
        idx = -1
        for i, o in enumerate(norm_opts):
            if txt and (txt in o or o in txt):
                idx = i
                break
    letters = ["a", "b", "c", "d", "e"]
    return letters[idx] if 0 <= idx < len(letters) else ""


def _choice_score(ans):
    ans = _normalize_answer(ans)
    if ans.startswith("a"):
        return 2
    if ans.startswith("b"):
        return 1
    return 0


def _parse_multiselect(ans):
    if ans is None:
        return set()
    raw = str(ans).strip()
    selected = set()
    for token in raw.replace("[", "").replace("]", "").replace('"', "").replace("'", "").split(","):
        t = token.strip().lower()
        if not t:
            continue
        if t and t[0] in {"a", "b", "c", "d", "e"}:
            selected.add(t[0])
    return selected


def _questionnaire_ranked_segments(user):
    pq = PostureQuestion.objects.filter(user=user).first()
    if not pq:
        return []

    q1_l = _coerce_letter(pq.forward_head_posture_answer, pq.forward_head_posture_options)
    q2_l = _coerce_letter(pq.gap_between_your_lower_back_answer, pq.gap_between_your_lower_back_options)
    q4_l = _coerce_letter(pq.slouch_when_standing_or_sitting_answer, pq.slouch_when_standing_or_sitting_options)
    q5_l = _coerce_letter(
        pq.feel_noticeably_shorter_end_of_day_compare_to_morning_answer,
        pq.feel_noticeably_shorter_end_of_day_compare_to_morning_options,
    )
    q7_l = _coerce_letter(
        pq.flexible_in_your_hamstrings_and_hips_answer,
        pq.flexible_in_your_hamstrings_and_hips_options,
    )
    q8_l = _coerce_letter(
        pq.active_your_core_during_daily_task_answer,
        pq.active_your_core_during_daily_task_options,
    )

    q1 = _choice_score(q1_l)
    q2 = _choice_score(q2_l)
    q4 = _choice_score(q4_l)
    q5 = _choice_score(q5_l)
    q7 = _choice_score(q7_l)
    q8 = _choice_score(q8_l)

    q3 = set()
    raw_q3 = pq.tightness_or_discomfort_answer
    try:
        parsed = json.loads(raw_q3) if isinstance(raw_q3, str) else raw_q3
    except Exception:
        parsed = raw_q3
    if isinstance(parsed, list):
        for item in parsed:
            l = _coerce_letter(item, pq.tightness_or_discomfort_options)
            if l:
                q3.add(l)
    else:
        q3 = _parse_multiselect(raw_q3)

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
    return sorted(scores.keys(), key=lambda s: (-scores[s], tie_order.get(s, 99)))


def _get_valid_variant(age, routine_type):
    track_map = {
        "POSTURE": [Track.ESSENTIALS, Track.POSTURE],
        "HGH": [Track.HGH],
    }

    age_bracket = (
        AgeBracket.objects.filter(min_age__lte=age)
        .filter(Q(max_age__gte=age) | Q(max_age__isnull=True))
        .order_by("-min_age")
        .first()
    )

    if not age_bracket:
        raise ValidationError("No suitable age bracket found")

    variants = (
        RoutineVariant.objects
        .filter(age_bracket=age_bracket, track__in=track_map[routine_type])
        .annotate(
            core_ex_count=Count(
                "prescriptions",
                filter=Q(prescriptions__tier=Tier.CORE),
            )
        )
        .order_by("template__name", "-core_ex_count")
    )

    if not variants.exists():
        raise ValidationError(f"No routine variant found for {routine_type}")

    return variants.first()


def _find_variant_exercise(variant, exercise, tier=None):
    if tier:
        ve = (
            VariantExercise.objects.filter(variant=variant, exercise=exercise, tier=tier)
            .order_by("order")
            .first()
        )
        if ve:
            return ve
    ve = VariantExercise.objects.filter(variant=variant, exercise=exercise).order_by("order").first()
    if ve:
        return ve
    # DB may use alias name on VariantExercise (e.g. "Doorways Chest Stretch") vs canonical Exercise row.
    key = spec_key_for_name(exercise.name)
    if not key:
        return None
    qs = VariantExercise.objects.filter(variant=variant).select_related("exercise")
    if tier:
        qs = qs.filter(tier=tier)
    for ve in qs.order_by("order"):
        if spec_key_for_name(ve.exercise.name) == key:
            return ve
    return None


def _core_from_variant(variant, *, teen: bool, allowed_categories=None):
    """Core 6 from VariantExercise; teen fallback fills fixed core names."""
    cats = allowed_categories or POSTURE_ALLOWED_CATEGORIES
    core = list(
        _variant_qs(variant, Tier.CORE, allowed_categories=cats)
        .select_related("exercise")
        .order_by("order")[:6]
    )
    if len(core) >= 6:
        return core[:6]

    if not teen:
        return core

    seen_ids = {ve.exercise_id for ve in core}
    for name in TEEN_CORE_6_NAMES:
        if len(core) >= 6:
            break
        ex = Exercise.objects.filter(name__iexact=name).first()
        if not ex or ex.id in seen_ids:
            for candidate in Exercise.objects.filter(spinal_pct__isnull=False):
                if spec_key_for_name(candidate.name) == spec_key_for_name(name):
                    ex = candidate
                    break
        if not ex or ex.id in seen_ids:
            continue
        ve = _find_variant_exercise(variant, ex, tier=Tier.CORE)
        if ve:
            core.append(ve)
            seen_ids.add(ex.id)
        else:
            pres = prescription_for_exercise_name(ex.name)
            core.append(
                _SyntheticVariantExercise(
                    variant=variant,
                    exercise=ex,
                    tier=Tier.CORE,
                    order=len(core) + 1,
                    **pres,
                )
            )
            seen_ids.add(ex.id)
    return core[:6]


class _SyntheticVariantExercise:
    """Minimal stand-in when no VariantExercise row exists for core fallback."""

    def __init__(self, variant, exercise, tier, order, sets, quantity_min, quantity_max=None, unit=Unit.REPS):
        self.variant = variant
        self.exercise = exercise
        self.tier = tier
        self.order = order
        self.sets = sets
        self.quantity_min = quantity_min
        self.quantity_max = quantity_max
        self.unit = unit
        self.id = None
        self.notes = ""
        self.type = Type.MAIN

    def get_type_display(self):
        return "Main"


def _variant_exercises_for_picks(variant, exercises, tier):
    """Map scored Exercise picks to VariantExercise on variant (prefer matching tier)."""
    out = []
    for ex in exercises:
        ve = _find_variant_exercise(variant, ex, tier=tier)
        if ve:
            out.append((ve, tier))
        else:
            pres = prescription_for_exercise_name(ex.name)
            out.append((
                _SyntheticVariantExercise(
                    variant=variant,
                    exercise=ex,
                    tier=tier,
                    order=len(out) + 1,
                    **pres,
                ),
                tier,
            ))
            logger.warning(
                "No VariantExercise for %s on variant %s; using prescription fallback",
                ex.name,
                variant,
            )
    return out


def build_posture_routine_slots(
    variant,
    age: int,
    optimization_breakdown: dict,
    section3_contract: dict | None = None,
):
    """
    Returns list of (variant_exercise_or_synthetic, tier) in order: 6 core, 2 rec, 2 beast.
    """
    losses = segment_losses_from_breakdown(optimization_breakdown, section3_contract)
    is_teen = 13 <= int(age) <= 20

    if is_teen:
        core = _core_from_variant(variant, teen=True)
        pool = list(teen_scoring_pool_queryset(Exercise))
        recommended, beast = select_teen_recommended_beast(pool, losses, age, [ve.exercise for ve in core])
    else:
        core = _core_from_variant(variant, teen=False, allowed_categories=POSTURE_ALLOWED_CATEGORIES)
        pool = list(adult_scoring_pool_queryset(Exercise))
        recommended, beast = select_adult_recommended_beast(pool, losses, [ve.exercise for ve in core])

    from workouts.exercise_assignment_data import dedupe_name_key

    slots = []
    seen_names: set[str] = set()
    seen_beast_keys: set[str] = set()

    def _append_slot(ve, tier):
        key = dedupe_name_key(getattr(ve.exercise, "name", "") or "")
        if tier == Tier.BEAST:
            # Beast whitelist may overlap core (Section 10.2); allow beast tier slots.
            if not key or key in seen_beast_keys:
                if key:
                    logger.warning(
                        "Skipping duplicate beast exercise %r",
                        ve.exercise.name,
                    )
                return
            seen_beast_keys.add(key)
            slots.append((ve, tier))
            return
        if not key or key in seen_names:
            if key:
                logger.warning(
                    "Skipping duplicate exercise %r in routine slots (tier=%s)",
                    ve.exercise.name,
                    tier,
                )
            return
        seen_names.add(key)
        slots.append((ve, tier))

    for ve in core:
        _append_slot(ve, Tier.CORE)
    for ve, tier in _variant_exercises_for_picks(variant, recommended, Tier.RECOMMENDED):
        _append_slot(ve, tier)
    for ve, tier in _variant_exercises_for_picks(variant, beast, Tier.BEAST):
        _append_slot(ve, tier)

    meta = {
        "assignment_spec": "v1",
        "losses_cm": losses,
        "ranked_segments": ranked_segments_from_losses(losses),
    }
    if is_teen:
        hgh_m, post_m = get_age_multipliers(age)
        meta["hgh_multiplier_applied"] = hgh_m
        meta["posture_multiplier_applied"] = post_m
        meta["age_used"] = age
    return slots, meta


# Legacy exports for tests that import old helpers
def assign_adult_exercises(variant, optimization_breakdown, ranked_segments=None):
    age = 25
    slots, _ = build_posture_routine_slots(variant, age, optimization_breakdown)
    return [s[0] for s in slots]


def assign_teen_posture_exercises(variant, optimization_breakdown, age, ranked_segments=None):
    slots, _ = build_posture_routine_slots(variant, age, optimization_breakdown)
    return [s[0] for s in slots]


def assign_teen_hgh_beast(variant, ranked_segments, age):
    return []


def _attach_posture_snapshot(routine, user) -> None:
    from users.models import PostureState
    from utils.posture.state_to_breakdown import posture_state_snapshot

    state = PostureState.objects.filter(user=user).first()
    routine.posture_snapshot_at_generation = posture_state_snapshot(state)
    routine.save(update_fields=["posture_snapshot_at_generation", "updated_at"])


def _persist_routine_exercises(routine, slots, *, start_order: int = 0) -> int:
    from workouts.exercise_assignment_data import dedupe_name_key

    seen_exercise_ids = set(
        UserRoutineExercise.objects.filter(routine=routine).values_list("exercise_id", flat=True)
    )
    seen_normalized_names: set[str] = set()
    seen_beast_names: set[str] = set()
    order = start_order
    for variant_ex, tier in slots:
        ex = variant_ex.exercise
        norm = dedupe_name_key(ex.name)
        if tier == Tier.BEAST:
            # Same Exercise row may appear as core + beast (Section 10.2 whitelist overlap).
            if norm and norm in seen_beast_names:
                continue
            if norm:
                seen_beast_names.add(norm)
        elif ex.id in seen_exercise_ids or (norm and norm in seen_normalized_names):
            continue
        else:
            seen_exercise_ids.add(ex.id)
            if norm:
                seen_normalized_names.add(norm)
        order += 1
        ve_id = variant_ex.id if getattr(variant_ex, "id", None) else None
        UserRoutineExercise.objects.create(
            routine=routine,
            variant_exercise_id=ve_id,
            exercise=ex,
            tier=tier,
            order=order,
            sets=variant_ex.sets,
            qty_min=variant_ex.quantity_min,
            qty_max=getattr(variant_ex, "quantity_max", None),
            unit=variant_ex.unit,
            notes=f"{tier.upper()} - posture assignment spec",
        )
    return order


@transaction.atomic
def generate_user_routines(
    user,
    optimization_breakdown,
    section3_contract=None,
    *,
    regen_rec_beast_only: bool = False,
    existing_routine=None,
):
    """Generate personalized POSTURE routine (10 exercises) using Exercise Assignment Spec."""
    age = get_user_age(user)
    if age is None:
        raise ValidationError("User age not found.")

    _get_program_config(age)
    variant = _get_valid_variant(age, "POSTURE")

    if regen_rec_beast_only and existing_routine is not None:
        return _regen_rec_beast_only(
            user,
            existing_routine,
            variant,
            age,
            optimization_breakdown,
            section3_contract,
        )

    UserRoutine.objects.filter(user=user, is_active=True).update(is_active=False)

    slots, assignment_meta = build_posture_routine_slots(
        variant, age, optimization_breakdown, section3_contract
    )

    scan_score = dict(optimization_breakdown or {})
    if isinstance(scan_score, dict):
        scan_score = {**scan_score, **assignment_meta}
    else:
        scan_score = assignment_meta

    routine = UserRoutine.objects.create(
        user=user,
        routine_type=RoutineType.POSTURE,
        is_active=True,
        scan_score=scan_score,
        optimization_breakdown=optimization_breakdown or {},
    )

    order = _persist_routine_exercises(routine, slots)
    if order < 10:
        logger.warning(
            "User %s posture routine has %s exercises (expected 10)",
            user.id,
            order,
        )

    _attach_posture_snapshot(routine, user)
    return [routine]


def _regen_rec_beast_only(
    user,
    routine,
    variant,
    age: int,
    optimization_breakdown: dict,
    section3_contract: dict | None,
):
    """Replace only Recommended + Beast slots; keep Core 6 on existing routine."""
    losses = segment_losses_from_breakdown(optimization_breakdown, section3_contract)
    is_teen = 13 <= int(age) <= 20

    core_exercises = list(
        UserRoutineExercise.objects.filter(routine=routine, tier=Tier.CORE)
        .select_related("exercise")
        .order_by("order")
    )
    core_ve_list = []
    for ure in core_exercises:
        if ure.variant_exercise_id:
            ve = VariantExercise.objects.filter(id=ure.variant_exercise_id).select_related("exercise").first()
            if ve:
                core_ve_list.append(ve)
                continue
        core_ve_list.append(
            _SyntheticVariantExercise(
                variant=variant,
                exercise=ure.exercise,
                tier=Tier.CORE,
                order=ure.order,
                sets=ure.sets,
                quantity_min=ure.qty_min,
                quantity_max=ure.qty_max,
                unit=ure.unit,
            )
        )

    core_ex_objs = [ve.exercise for ve in core_ve_list]
    if is_teen:
        pool = list(teen_scoring_pool_queryset(Exercise))
        recommended, beast = select_teen_recommended_beast(pool, losses, age, core_ex_objs)
    else:
        pool = list(adult_scoring_pool_queryset(Exercise))
        recommended, beast = select_adult_recommended_beast(pool, losses, core_ex_objs)

    UserRoutineExercise.objects.filter(
        routine=routine,
        tier__in=[Tier.RECOMMENDED, Tier.BEAST],
    ).delete()

    rec_beast_slots = []
    for ve, tier in _variant_exercises_for_picks(variant, recommended, Tier.RECOMMENDED):
        rec_beast_slots.append((ve, tier))
    for ve, tier in _variant_exercises_for_picks(variant, beast, Tier.BEAST):
        rec_beast_slots.append((ve, tier))

    core_count = len(core_exercises)
    order = _persist_routine_exercises(routine, rec_beast_slots, start_order=core_count)

    assignment_meta = {
        "assignment_spec": "v1",
        "losses_cm": losses,
        "ranked_segments": ranked_segments_from_losses(losses),
        "partial_regen": True,
    }
    if is_teen:
        hgh_m, post_m = get_age_multipliers(age)
        assignment_meta["hgh_multiplier_applied"] = hgh_m
        assignment_meta["posture_multiplier_applied"] = post_m
        assignment_meta["age_used"] = age

    scan_score = dict(routine.scan_score or {})
    scan_score.update(assignment_meta)
    scan_score["routine_regenerated"] = True
    routine.scan_score = scan_score
    routine.optimization_breakdown = optimization_breakdown or {}
    routine.save(update_fields=["scan_score", "optimization_breakdown", "updated_at"])

    if order < 10:
        logger.warning(
            "User %s partial regen has %s exercises (expected 10)",
            user.id,
            order,
        )

    _attach_posture_snapshot(routine, user)
    return [routine]
