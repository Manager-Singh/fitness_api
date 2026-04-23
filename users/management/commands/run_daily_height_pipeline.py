from datetime import datetime

from django.core.management.base import BaseCommand

from users.spec_runtime import compute_daily_height_for_user, users_for_runtime
from utils.user_time import user_today

import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run daily Section-14 style height compute pipeline."

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, help="Optional YYYY-MM-DD date.")

    def handle(self, *args, **options):
        log_date = None
        if options.get("date"):
            log_date = datetime.strptime(options["date"], "%Y-%m-%d").date()

        total = 0
        for user in users_for_runtime():
            effective_date = log_date or user_today(user)
            # Docx: prevent double-run per local day (DST/travel safety).
            last_reset = getattr(user, "last_reset_date", None)
            if last_reset is not None and effective_date <= last_reset:
                continue
            compute_daily_height_for_user(user, log_date=effective_date)
            try:
                user.last_reset_date = effective_date
                user.save(update_fields=["last_reset_date"])
            except Exception:
                logger.exception(
                    "Failed persisting last_reset_date during daily pipeline",
                    extra={"user_id": getattr(user, "id", None), "effective_date": str(effective_date)},
                )
            total += 1
        self.stdout.write(self.style.SUCCESS(f"Processed daily pipeline for {total} users."))
