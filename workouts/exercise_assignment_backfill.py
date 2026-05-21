"""Backfill Exercise rows from Exercise Assignment Spec (shared by migration + management command)."""
from __future__ import annotations

from workouts.exercise_assignment_data import (
    EXERCISE_ASSIGNMENT_SPEC,
    apply_spec_to_exercise_dict,
    spec_key_for_name,
)
from workouts.models import Exercise


def run_backfill(*, stdout=None) -> dict:
    updated = 0
    created = 0
    unmatched = []

    for ex in Exercise.objects.all():
        key = spec_key_for_name(ex.name)
        if not key:
            unmatched.append(ex.name)
            continue
        spec = EXERCISE_ASSIGNMENT_SPEC[key]
        for field, value in apply_spec_to_exercise_dict(spec).items():
            setattr(ex, field, value)
        if spec.get("category"):
            ex.category = spec["category"]
        if spec.get("points") is not None:
            ex.points = spec["points"]
        ex.save()
        updated += 1

    for key, spec in EXERCISE_ASSIGNMENT_SPEC.items():
        canonical = spec["name"]
        if Exercise.objects.filter(name__iexact=canonical).exists():
            continue
        if any(spec_key_for_name(ex.name) == key for ex in Exercise.objects.all()):
            continue
        Exercise.objects.create(
            name=canonical,
            **apply_spec_to_exercise_dict(spec),
            category=spec.get("category", "general"),
            points=spec.get("points", 0),
        )
        created += 1

    ready = Exercise.objects.filter(
        spinal_pct__isnull=False,
        potency__isnull=False,
        teen_only=False,
    ).count()

    if stdout:
        stdout.write(f"Updated {updated} exercises, created {created} canonical rows.")
        stdout.write(f"Adult scoring pool ready: {ready} exercises.")
        if unmatched:
            stdout.write(f"Unmatched (no spec row): {len(unmatched)}")
            for name in unmatched[:15]:
                stdout.write(f"  - {name}")
            if len(unmatched) > 15:
                stdout.write(f"  ... and {len(unmatched) - 15} more")

    return {"updated": updated, "created": created, "pool_ready": ready, "unmatched": unmatched}
