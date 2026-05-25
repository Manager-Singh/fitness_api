"""Merge duplicate Exercise rows that share the same canonical assignment spec key."""
from django.core.management.base import BaseCommand
from django.db import transaction

from workouts.exercise_assignment_data import dedupe_name_key, spec_key_for_name
from workouts.models import Exercise, UserRoutineExercise, VariantExercise, WorkoutEntry


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
            canonical = rows[0]
            dupes = rows[1:]
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
    def _repoint_and_delete(canonical: Exercise, dup: Exercise) -> None:
        for ure in UserRoutineExercise.objects.filter(exercise=dup).select_related("routine"):
            clash = UserRoutineExercise.objects.filter(
                routine=ure.routine, exercise=canonical
            ).first()
            if clash:
                ure.delete()
            else:
                ure.exercise = canonical
                ure.save(update_fields=["exercise"])
        VariantExercise.objects.filter(exercise=dup).update(exercise=canonical)
        WorkoutEntry.objects.filter(exercise=dup).update(exercise=canonical)
        dup.delete()
