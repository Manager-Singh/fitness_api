from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from workouts.exercise_catalog_import import ensure_seconds_per_rep_column, import_catalog_csv


class Command(BaseCommand):
    help = (
        "Import client-fixed exercise catalog CSV into Exercise + VariantExercise "
        "(copy, instructions, seconds_per_rep, timers)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            default="EXERCISE_CATALOG_DATABASE_EXPORT_fixed_by_client.csv",
            help="Path to client CSV (default: project root)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report changes without saving.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv"])
        if not csv_path.is_absolute():
            csv_path = Path(settings.BASE_DIR) / csv_path
        if not csv_path.exists():
            self.stderr.write(self.style.ERROR(f"CSV not found: {csv_path}"))
            return

        if ensure_seconds_per_rep_column():
            self.stdout.write("Added workouts_exercise.seconds_per_rep column.")

        summary = import_catalog_csv(csv_path, dry_run=options["dry_run"])
        verb = "Would update" if options["dry_run"] else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {summary['exercises_updated']} exercise(s), "
                f"{summary['variants_updated']} variant prescription(s) "
                f"from {summary['rows']} CSV row(s)."
            )
        )
        for w in summary["warnings"][:30]:
            self.stdout.write(self.style.WARNING(w))
        if len(summary["warnings"]) > 30:
            self.stdout.write(f"... and {len(summary['warnings']) - 30} more warnings")
