from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from users.spec_runtime import rebuild_ledger_from_date


class Command(BaseCommand):
    help = "Section 14.2 — rebuild HeightLedger from a local log date onward for one user."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, required=True)
        parser.add_argument("--from-date", type=str, required=True, help="YYYY-MM-DD")

    def handle(self, *args, **options):
        uid = options["user_id"]
        try:
            from_date = datetime.strptime(options["from_date"], "%Y-%m-%d").date()
        except ValueError as e:
            raise CommandError("Invalid --from-date; use YYYY-MM-DD.") from e

        User = get_user_model()
        try:
            user = User.objects.get(pk=uid)
        except User.DoesNotExist as e:
            raise CommandError(f"User id={uid} not found.") from e

        out = rebuild_ledger_from_date(user, from_date)
        self.stdout.write(self.style.SUCCESS(str(out)))
