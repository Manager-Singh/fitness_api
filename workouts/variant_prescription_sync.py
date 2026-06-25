"""
Sync and validate RoutineVariant ↔ VariantExercise attachments for Exercise Assignment Spec.
Used by Django admin actions and management command.
"""
from __future__ import annotations

import logging
from typing import Iterable

from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from workouts.exercise_assignment_data import (
    ADULT_CORE_6_BY_MIN_AGE,
    TEEN_CORE_6_NAMES,
    TEEN_HGH_POOL_CANONICAL_NAMES,
    TEEN_POSTURE_POOL_CANONICAL_NAMES,
    ADULT_POSTURE_POOL_CANONICAL_NAMES,
    is_teen_only_exercise,
    normalize_exercise_name,
    spec_key_for_name,
)
from workouts.models import Exercise, RoutineVariant, Tier, Track, VariantExercise
from utils.exercise_prescriptions import prescription_for_exercise_name

logger = logging.getLogger(__name__)

POSTURE_TRACKS = {Track.ESSENTIALS, Track.POSTURE}


def variant_is_teen(variant: RoutineVariant) -> bool:
    bracket = variant.age_bracket
    if bracket.max_age is not None and bracket.max_age <= 20:
        return True
    return bracket.min_age < 21


def variant_is_posture(variant: RoutineVariant) -> bool:
    return variant.track in POSTURE_TRACKS


def adult_core_names_for_bracket(min_age: int) -> list[str]:
    keys = sorted(ADULT_CORE_6_BY_MIN_AGE.keys(), reverse=True)
    for k in keys:
        if min_age >= k:
            return list(ADULT_CORE_6_BY_MIN_AGE[k])
    return list(ADULT_CORE_6_BY_MIN_AGE[21])


def resolve_exercise_by_canonical_name(name: str) -> Exercise | None:
    """Find Exercise row by canonical or alias name."""
    ex = Exercise.objects.filter(name__iexact=name).first()
    if ex:
        return ex
    key = spec_key_for_name(name)
    if not key:
        return None
    for candidate in Exercise.objects.filter(spinal_pct__isnull=False):
        if spec_key_for_name(candidate.name) == key:
            return candidate
    return None


def audit_variant(variant: RoutineVariant) -> list[str]:
    """Return human-readable issues for this variant."""
    issues = []
    if not variant_is_posture(variant):
        return issues

    teen = variant_is_teen(variant)
    prescriptions = variant.prescriptions.select_related("exercise").all()

    for ve in prescriptions:
        ex = ve.exercise
        if not teen and is_teen_only_exercise(ex):
            issues.append(
                f"Adult variant has teen-only exercise: {ex.name} (tier={ve.tier}, order={ve.order})"
            )
        if teen and ve.tier in (Tier.RECOMMENDED, Tier.BEAST) and ex.teen_only:
            pass  # allowed in beast/rec for teens
        # Legacy/custom exercises without spec matrix are ignored (not used by scorer).

    core_rows = [ve for ve in prescriptions if ve.tier == Tier.CORE]
    expected_core = TEEN_CORE_6_NAMES if teen else adult_core_names_for_bracket(variant.age_bracket.min_age)
    core_names = [ve.exercise.name for ve in sorted(core_rows, key=lambda x: x.order)]
    if len(core_rows) < 6:
        issues.append(f"Only {len(core_rows)} core rows (expected 6). Have: {core_names}")
    else:
        missing = []
        for expected in expected_core:
            if not any(spec_key_for_name(n) == spec_key_for_name(expected) for n in core_names):
                missing.append(expected)
        if missing:
            issues.append(f"Core 6 missing expected names: {missing}")

    return issues


def _pick_adult_swap_exercise(variant: RoutineVariant, *, exclude_exercise_id: int) -> Exercise | None:
    """Adult posture exercise not already on this variant (for protected-row swap)."""
    attached = set(variant.prescriptions.values_list("exercise_id", flat=True))
    for name in ADULT_POSTURE_POOL_CANONICAL_NAMES:
        ex = resolve_exercise_by_canonical_name(name)
        if not ex or is_teen_only_exercise(ex):
            continue
        if ex.id == exclude_exercise_id or ex.id in attached:
            continue
        return ex
    return None


def _detach_teen_only_row(
    ve: VariantExercise, variant: RoutineVariant, stats: dict, *, dry_run: bool
) -> None:
    """Remove teen-only VariantExercise from an adult variant; swap if PROTECT blocks delete."""
    if dry_run:
        stats["removed"] += 1
        return
    try:
        ve.delete()
        stats["removed"] += 1
        return
    except ProtectedError:
        pass

    replacement = _pick_adult_swap_exercise(variant, exclude_exercise_id=ve.exercise_id)
    if not replacement:
        stats["skipped_protected"] += 1
        stats["issues"].append(
            f"Could not remove teen-only {ve.exercise.name} (tier={ve.tier}): "
            f"referenced by user routines — regenerate affected users"
        )
        return

    old_name = ve.exercise.name
    try:
        ve.exercise = replacement
        ve.save(update_fields=["exercise"])
        stats["reassigned"] += 1
        stats["issues"].append(
            f"Replaced {old_name} → {replacement.name} on protected row (tier={ve.tier}); "
            f"regenerate user routines to refresh live assignments"
        )
    except IntegrityError:
        stats["skipped_protected"] += 1
        stats["issues"].append(
            f"Could not replace {old_name}: {replacement.name} already on variant — "
            f"regenerate user routines"
        )


def _default_prescription_fields(exercise: Exercise) -> dict:
    pres = prescription_for_exercise_name(exercise.name)
    return {
        "sets": pres.get("sets", 2),
        "quantity_min": pres.get("quantity_min", 10),
        "quantity_max": pres.get("quantity_max"),
        "unit": pres.get("unit", "reps"),
    }


@transaction.atomic
def sync_variant_prescriptions(variant: RoutineVariant, *, dry_run: bool = False) -> dict:
    """
    Align VariantExercise rows with spec:
    - Remove teen-only exercises from adult posture variants
    - Ensure Core 6 by age band
    - Attach posture pool exercises for rec/beast prescription lookup
    """
    stats = {
        "removed": 0,
        "reassigned": 0,
        "skipped_protected": 0,
        "core_upserted": 0,
        "pool_upserted": 0,
        "issues": [],
    }

    if not variant_is_posture(variant):
        stats["issues"].append("Skipped: not a posture track variant")
        return stats

    teen = variant_is_teen(variant)
    bracket_min = variant.age_bracket.min_age

    # 1) Remove teen-only from adult variants (by flag or known HGH names)
    if not teen:
        for ve in variant.prescriptions.select_related("exercise").all():
            if is_teen_only_exercise(ve.exercise):
                _detach_teen_only_row(ve, variant, stats, dry_run=dry_run)

    # 2) Core 6
    core_names = TEEN_CORE_6_NAMES if teen else adult_core_names_for_bracket(bracket_min)
    for order, canonical in enumerate(core_names, start=1):
        ex = resolve_exercise_by_canonical_name(canonical)
        if not ex:
            stats["issues"].append(f"Exercise not in DB: {canonical}")
            continue
        if dry_run:
            stats["core_upserted"] += 1
            continue
        pres = _default_prescription_fields(ex)
        ve, created = VariantExercise.objects.update_or_create(
            variant=variant,
            exercise=ex,
            defaults={
                "order": order,
                "tier": Tier.CORE,
                "type": _default_type_for_exercise(ex.name),
                **pres,
            },
        )
        if created or ve.tier != Tier.CORE or ve.order != order:
            ve.tier = Tier.CORE
            ve.order = order
            ve.save(update_fields=["tier", "order", "sets", "quantity_min", "quantity_max", "unit"])
        stats["core_upserted"] += 1

    core_exercise_ids = set(
        variant.prescriptions.filter(tier=Tier.CORE).values_list("exercise_id", flat=True)
    )

    # 3) Pool rows (for scorer picks — attach as rec tier, high order)
    if teen:
        pool_names = list(TEEN_POSTURE_POOL_CANONICAL_NAMES) + list(TEEN_HGH_POOL_CANONICAL_NAMES)
    else:
        pool_names = list(ADULT_POSTURE_POOL_CANONICAL_NAMES)

    order_base = 20
    for i, canonical in enumerate(pool_names):
        ex = resolve_exercise_by_canonical_name(canonical)
        if not ex or ex.id in core_exercise_ids:
            continue
        if not teen and is_teen_only_exercise(ex):
            continue
        if dry_run:
            stats["pool_upserted"] += 1
            continue
        tier = Tier.BEAST if (ex.beast_bonus or 0) >= 2 and (ex.potency or 0) >= 7 else Tier.RECOMMENDED
        pres = _default_prescription_fields(ex)
        VariantExercise.objects.update_or_create(
            variant=variant,
            exercise=ex,
            defaults={
                "order": order_base + i,
                "tier": tier,
                "type": _default_type_for_exercise(ex.name),
                **pres,
            },
        )
        stats["pool_upserted"] += 1

    stats["issues"].extend(audit_variant(variant))
    return stats


def _default_type_for_exercise(name: str):
    from workouts.models import Type

    key = spec_key_for_name(name) or normalize_exercise_name(name)
    if key in ("hamstring stretch", "deep squat hold", "butterfly stretch", "lunges", "box jumps / jump squats", "bodyweight squats", "squats", "seated forward fold"):
        return Type.LEGHAMSTRING
    if key in ("doorway chest stretch", "tadasana (mountain pose)", "chin tucks", "wall angels", "foam roller thoracic extension", "superman hold"):
        return Type.POSTURALCOLLAPSE
    if key in ("hip flexor stretch", "glute bridges", "pelvic tilts", "plank", "bird-dog"):
        return Type.PELCIVTILTBACK
    return Type.SPINALCPMPRESSION


def sync_all_posture_variants(*, dry_run: bool = False) -> list[dict]:
    results = []
    qs = RoutineVariant.objects.filter(track__in=POSTURE_TRACKS).select_related(
        "age_bracket", "template"
    )
    for variant in qs:
        stats = sync_variant_prescriptions(variant, dry_run=dry_run)
        stats["variant"] = str(variant)
        stats["variant_id"] = variant.id
        results.append(stats)
    return results
