from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run full spec runtime cycle: compute + cleanup + notifications."

    def handle(self, *args, **options):
        call_command("run_daily_height_pipeline")
        call_command("cleanup_expired_invites")
        call_command("send_runtime_push_notifications")
        self.stdout.write(self.style.SUCCESS("Spec runtime cycle completed."))
