from django.core.management.base import BaseCommand

from workouts.exercise_assignment_backfill import run_backfill


class Command(BaseCommand):
    help = (
        "Backfill Exercise assignment spec fields (segment %, potency, teen_only, etc.) "
        "on existing DB rows. Run after makemigrations/migrate if migration has no RunPython."
    )

    def handle(self, *args, **options):
        run_backfill(stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS("Backfill complete."))
