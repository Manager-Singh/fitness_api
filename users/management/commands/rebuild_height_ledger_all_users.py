from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from users.spec_runtime import rebuild_ledger_from_date


class Command(BaseCommand):
    help = (
        "Section 14.2 — rebuild HeightLedger from a date onward for all active users "
        "(or a comma-separated --user-ids list)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--from-date", type=str, required=True, help="YYYY-MM-DD")
        parser.add_argument(
            "--user-ids",
            type=str,
            default="",
            help="Optional comma-separated user IDs; default = all active users.",
        )
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            help="Include inactive users when --user-ids is not set.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List users that would be rebuilt without writing changes.",
        )

    def handle(self, *args, **options):
        try:
            from_date = datetime.strptime(options["from_date"], "%Y-%m-%d").date()
        except ValueError as e:
            raise CommandError("Invalid --from-date; use YYYY-MM-DD.") from e

        User = get_user_model()
        raw_ids = (options.get("user_ids") or "").strip()
        if raw_ids:
            try:
                ids = [int(x.strip()) for x in raw_ids.split(",") if x.strip()]
            except ValueError as e:
                raise CommandError("Invalid --user-ids; use comma-separated integers.") from e
            users = User.objects.filter(pk__in=ids).order_by("id")
            missing = set(ids) - set(users.values_list("id", flat=True))
            if missing:
                self.stderr.write(
                    self.style.WARNING(f"User IDs not found (skipped): {sorted(missing)}")
                )
        else:
            qs = User.objects.all().order_by("id")
            if not options.get("include_inactive"):
                qs = qs.filter(is_active=True)
            users = qs

        total = users.count()
        if total == 0:
            self.stdout.write("No users matched.")
            return

        if options.get("dry_run"):
            self.stdout.write(
                f"DRY RUN: would rebuild {total} user(s) from {from_date}"
            )
            for u in users.iterator():
                self.stdout.write(f"  user_id={u.id} username={u.username}")
            return

        ok = 0
        errors = 0
        for u in users.iterator():
            try:
                out = rebuild_ledger_from_date(u, from_date)
                ok += 1
                self.stdout.write(
                    f"user_id={u.id} days_rebuilt={out.get('days_rebuilt')} from_date={out.get('from_date')}"
                )
            except Exception as e:
                errors += 1
                self.stderr.write(
                    self.style.ERROR(f"user_id={u.id} failed: {e}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {ok} rebuilt, {errors} failed, {total} total (from_date={from_date})"
            )
        )
        if errors:
            raise CommandError(f"{errors} user(s) failed rebuild.")
