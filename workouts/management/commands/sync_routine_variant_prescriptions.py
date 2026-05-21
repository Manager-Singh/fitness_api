from django.core.management.base import BaseCommand

from workouts.variant_prescription_sync import sync_all_posture_variants


class Command(BaseCommand):
    help = (
        "Sync RoutineVariant exercise attachments from Exercise Assignment Spec: "
        "Core 6 per age band, posture pool for rec/beast, remove teen-only from adult variants."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report counts only; do not write to DB.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        results = sync_all_posture_variants(dry_run=dry_run)
        for stats in results:
            self.stdout.write(
                f"{stats.get('variant')}: removed={stats['removed']} "
                f"core={stats['core_upserted']} pool={stats['pool_upserted']}"
            )
            for issue in stats.get("issues", []):
                self.stdout.write(self.style.WARNING(f"  - {issue}"))
        self.stdout.write(self.style.SUCCESS(f"Processed {len(results)} posture variant(s)."))
