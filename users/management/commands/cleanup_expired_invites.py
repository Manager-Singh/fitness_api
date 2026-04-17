from django.core.management.base import BaseCommand
from django.utils import timezone

from users.models import FriendInvite


class Command(BaseCommand):
    help = "Delete expired and unaccepted friend invites."

    def handle(self, *args, **options):
        qs = FriendInvite.objects.filter(expires_at__lt=timezone.now(), accepted_by__isnull=True)
        count = qs.count()
        qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} expired invites."))
