"""Resync stored UserRoutineExercise dosage from the linked catalog prescription.

HEIGHT_APP_FIX_CHECKLIST items 1 & 3: existing users' saved routines still hold
the OLD dosage (e.g. "3 sets x 15 reps") while the catalog (VariantExercise) has
been updated to "2 sets x 20 reps". The serializer already prefers the live
catalog, but this command also corrects the stored rows so the DB itself is
consistent (no stale 15-rep values anywhere).

It copies sets / quantity_min / quantity_max / unit from each row's linked
VariantExercise. It does NOT touch `notes` (that holds the assignment label) or
any logging/points/ledger data.

Usage:
    python manage.py resync_user_routine_dosage_from_variant --dry-run
    python manage.py resync_user_routine_dosage_from_variant --user qqqq@yopmail.com
    python manage.py resync_user_routine_dosage_from_variant          # all users
"""
from collections import Counter

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from workouts.models import UserRoutineExercise


class Command(BaseCommand):
    help = "Resync UserRoutineExercise sets/qty/unit from the linked VariantExercise catalog prescription."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report changes without writing.")
        parser.add_argument("--user", default=None, help="Limit to one user by id, email, or username.")

    def _resolve_user_ids(self, user_arg):
        if not user_arg:
            return None
        User = get_user_model()
        cond = Q(email__iexact=user_arg) | Q(username__iexact=user_arg)
        if str(user_arg).isdigit():
            cond = cond | Q(pk=int(user_arg))
        return set(User.objects.filter(cond).values_list("id", flat=True))

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        user_ids = self._resolve_user_ids(options.get("user"))

        qs = (
            UserRoutineExercise.objects.filter(variant_exercise__isnull=False)
            .select_related("variant_exercise", "exercise")
        )
        if user_ids is not None:
            if not user_ids:
                self.stdout.write(self.style.WARNING("No matching user found."))
                return
            qs = qs.filter(routine__user_id__in=user_ids)

        scanned = 0
        changed = 0
        by_exercise = Counter()
        to_update = []

        for ure in qs.iterator():
            ve = ure.variant_exercise
            scanned += 1
            old = (ure.sets, ure.qty_min, ure.qty_max, ure.unit)
            new = (ve.sets, ve.quantity_min, ve.quantity_max, ve.unit)
            if old == new:
                continue
            changed += 1
            by_exercise[ure.exercise.name] += 1
            ure.sets, ure.qty_min, ure.qty_max, ure.unit = new
            to_update.append(ure)

        for name, n in sorted(by_exercise.items(), key=lambda kv: -kv[1]):
            self.stdout.write(f"  {name}: {n} row(s) to fix")

        if not dry_run and to_update:
            with transaction.atomic():
                UserRoutineExercise.objects.bulk_update(
                    to_update, ["sets", "qty_min", "qty_max", "unit"], batch_size=500
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. scanned={scanned}, changed={changed}, dry_run={dry_run}"
            )
        )
