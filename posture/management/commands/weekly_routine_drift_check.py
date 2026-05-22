"""Weekly drift check: regen Rec+Beast when posture shifted >= 15% since generation."""
from django.core.management.base import BaseCommand

from users.models import PostureState, User
from utils.routine_regeneration_check import check_and_maybe_regenerate_routine


class Command(BaseCommand):
    help = "Re-check active routines against current PostureState (15% segment threshold)"

    def handle(self, *args, **options):
        users = User.objects.filter(
            posture_state__scan_completed=True,
            custom_routines__is_active=True,
        ).distinct()

        regen_count = 0
        for user in users:
            state = PostureState.objects.filter(user=user).first()
            if not state:
                continue
            if check_and_maybe_regenerate_routine(user):
                regen_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Routines regenerated for {regen_count} user(s)")
        )
