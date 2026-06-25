from django.core.management.base import BaseCommand

from workouts.exercise_spec_sheet_sync import run_sync


class Command(BaseCommand):
    help = (
        "Sync Exercise description, instruction_methods (3 steps), instruction_steps, "
        "and safety_note from EXERCISE_SPEC_SHEET.md canonical data."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many rows would change without saving.",
        )

    def handle(self, *args, **options):
        result = run_sync(dry_run=options["dry_run"], stdout=self.stdout)
        if result["updated"] and not options["dry_run"]:
            self.stdout.write(self.style.SUCCESS(f"Done — {result['updated']} exercise(s) synced."))
