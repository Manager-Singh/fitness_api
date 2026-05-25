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
    def _merge_ure(canonical: Exercise, ure: UserRoutineExercise) -> None:
        """Point ure at canonical exercise or drop if routine already has canonical."""
        clash = (
            UserRoutineExercise.objects.filter(routine=ure.routine, exercise=canonical)
            .exclude(pk=ure.pk)
            .first()
        )
        if clash:
            if ure.variant_exercise_id and clash.variant_exercise_id is None:
                clash.variant_exercise = ure.variant_exercise
                clash.save(update_fields=["variant_exercise"])
            ure.delete()
            return
        ure.exercise = canonical
        ure.save(update_fields=["exercise"])

    @staticmethod
    def _repoint_and_delete(canonical: Exercise, dup: Exercise) -> None:
        # 1) VariantExercise rows + linked UserRoutineExercise (variant_exercise PROTECT).
        for ve_dup in list(VariantExercise.objects.filter(exercise=dup)):
            ve_canon = VariantExercise.objects.filter(
                variant=ve_dup.variant, exercise=canonical
            ).first()
            for ure in list(UserRoutineExercise.objects.filter(variant_exercise=ve_dup)):
                if ve_canon:
                    clash = (
                        UserRoutineExercise.objects.filter(
                            routine=ure.routine, exercise=canonical
                        )
                        .exclude(pk=ure.pk)
                        .first()
                    )
                    if clash:
                        ure.delete()
                    else:
                        ure.variant_exercise = ve_canon
                        ure.exercise = canonical
                        ure.save(update_fields=["variant_exercise", "exercise"])
                else:
                    Command._merge_ure(canonical, ure)
            if ve_canon:
                ve_dup.delete()
            else:
                ve_dup.exercise = canonical
                ve_dup.save(update_fields=["exercise"])

        # 2) Any remaining routine rows still pointing at duplicate exercise id.
        for ure in list(UserRoutineExercise.objects.filter(exercise=dup)):
            Command._merge_ure(canonical, ure)

        WorkoutEntry.objects.filter(exercise=dup).update(exercise=canonical)
        dup.delete()
