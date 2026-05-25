"""Merge duplicate Exercise rows that share the same canonical assignment spec key."""
from django.core.management.base import BaseCommand
from django.db import transaction

from workouts.exercise_assignment_data import (
    EXERCISE_ASSIGNMENT_SPEC,
    dedupe_name_key,
    spec_key_for_name,
)
from workouts.models import Exercise, UserRoutineExercise, VariantExercise, WorkoutEntry


def _pick_canonical_row(key: str, rows: list[Exercise]) -> tuple[Exercise, list[Exercise]]:
    """Prefer spec canonical name, then row with photo, then lowest id."""
    spec_name = (EXERCISE_ASSIGNMENT_SPEC.get(key) or {}).get("name")

    def sort_key(ex: Exercise) -> tuple:
        name_match = 0
        if spec_name and ex.name.strip().lower() == spec_name.strip().lower():
            name_match = 1
        has_photo = 1 if ex.photo else 0
        return (-name_match, -has_photo, ex.id)

    ordered = sorted(rows, key=sort_key)
    return ordered[0], ordered[1:]


class Command(BaseCommand):
    help = "Merge duplicate Exercise rows (same canonical spec key) into one canonical row."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print planned merges without writing.",
        )
        parser.add_argument(
            "--key",
            type=str,
            default="",
            help="Optional single canonical key (e.g. doorway chest stretch).",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        only_key = (options.get("key") or "").strip().lower()

        by_key: dict[str, list[Exercise]] = {}
        for ex in Exercise.objects.all().order_by("id"):
            key = dedupe_name_key(ex.name) or spec_key_for_name(ex.name)
            if not key:
                continue
            if only_key and key != only_key:
                continue
            by_key.setdefault(key, []).append(ex)

        merged = 0
        for key, rows in sorted(by_key.items()):
            if len(rows) < 2:
                continue
            canonical, dupes = _pick_canonical_row(key, rows)
            self.stdout.write(f"{key}: keep id={canonical.id} {canonical.name!r}")
            for dup in dupes:
                self.stdout.write(f"  merge id={dup.id} {dup.name!r}")
                if dry_run:
                    continue
                with transaction.atomic():
                    self._repoint_and_delete(canonical, dup)
                merged += 1

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes written."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Merged {merged} duplicate exercise row(s)."))

    @staticmethod
    def _repoint_fk(canonical: Exercise, dup: Exercise, model, *, routine_field=None) -> None:
        qs = model.objects.filter(exercise=dup)
        if routine_field:
            for row in qs.select_related(routine_field):
                parent = getattr(row, routine_field)
                clash = model.objects.filter(**{routine_field: parent, "exercise": canonical}).first()
                if clash:
                    row.delete()
                else:
                    row.exercise = canonical
                    row.save(update_fields=["exercise"])
            return
        if model is VariantExercise:
            for ve in qs:
                clash = VariantExercise.objects.filter(
                    variant=ve.variant, exercise=canonical
                ).first()
                if clash:
                    ve.delete()
                else:
                    ve.exercise = canonical
                    ve.save(update_fields=["exercise"])
            return
        qs.update(exercise=canonical)

    def _repoint_and_delete(self, canonical: Exercise, dup: Exercise) -> None:
        self._repoint_fk(canonical, dup, UserRoutineExercise, routine_field="routine")
        self._repoint_fk(canonical, dup, VariantExercise)
        WorkoutEntry.objects.filter(exercise=dup).update(exercise=canonical)
        dup.delete()
