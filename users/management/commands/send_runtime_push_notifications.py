from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from nutration.models_log import NutraEntry
from user_profile.models import UserProfile
from utils.age import get_user_age
from utils.check_payment import check_subscription_or_response
from utils.fcm import send_push_fcm
from workouts.models import WorkoutEntry
from users.models import NotificationEventLog

from users.spec_runtime import users_for_notifications
from utils.user_time import user_now, user_today


class Command(BaseCommand):
    help = "Send spec runtime push notifications (trial/rescan/streak-at-risk)."

    @staticmethod
    def _send_once(user, token, event_key, today, title, body, data):
        existing = NotificationEventLog.objects.filter(
            user=user,
            event_key=event_key,
            event_date=today,
        ).exists()
        if existing:
            return False
        send_push_fcm(token, title, body, data)
        NotificationEventLog.objects.create(
            user=user,
            event_key=event_key,
            event_date=today,
            payload=data or {},
        )
        return True

    def handle(self, *args, **options):
        now = timezone.now()
        users, today = users_for_notifications(now=now)
        sent = 0
        for user in users:
            local_now = user_now(user)
            hhmm = (local_now.hour, local_now.minute)
            user_date = user_today(user)
            token = (user.fcm_token or "").strip()
            if not token:
                continue

            try:
                age = get_user_age(user)
            except Exception:
                age = 0
            profile = UserProfile.objects.filter(user=user).first()
            if not profile:
                continue
            sub = check_subscription_or_response(user).data

            # Day 6 warning for teen trial.
            trial_day = sub.get("trial_day")
            if age < 21 and sub.get("is_trial") and trial_day == 6 and hhmm == (9, 0):
                if self._send_once(
                    user,
                    token,
                    "trial_day6_warning",
                    user_date,
                    "Trial ending soon",
                    "1 day left on your free trial. Upgrade to keep GrowthMax+ gains active.",
                    {"event": "trial_day6_warning"},
                ):
                    sent += 1

            # Day 7 expiry notice for unpaid teens.
            if age < 21 and not sub.get("is_paid") and trial_day and int(trial_day) >= 7 and hhmm == (23, 59):
                if self._send_once(
                    user,
                    token,
                    "trial_expired",
                    user_date,
                    "Trial ended",
                    "Your GrowthMax+ gains are paused. Subscribe to resume progression.",
                    {"event": "trial_expired"},
                ):
                    sent += 1

            # Re-scan ready every 7 days.
            if profile.last_scan:
                days_since_scan = (user_date - profile.last_scan.date()).days
                if days_since_scan >= 7 and hhmm == (0, 0):
                    msg = "Your weekly re-scan is ready."
                    if age < 21 and not sub.get("is_paid"):
                        msg = "Upgrade to unlock your weekly re-scan."
                    if self._send_once(
                        user,
                        token,
                        "rescan_ready",
                        user_date,
                        "Re-scan ready",
                        msg,
                        {"event": "rescan_ready", "days_since_scan": str(days_since_scan)},
                    ):
                        sent += 1

            # Streak-at-risk heuristic: activity yesterday but none today.
            yesterday = user_date - timedelta(days=1)
            had_workout_yesterday = WorkoutEntry.objects.filter(session__user=user, session__date=yesterday).exists()
            had_nutra_yesterday = NutraEntry.objects.filter(session__user=user, session__date=yesterday).exists()
            has_workout_today = WorkoutEntry.objects.filter(session__user=user, session__date=user_date).exists()
            has_nutra_today = NutraEntry.objects.filter(session__user=user, session__date=user_date).exists()
            if hhmm == (21, 0) and (had_workout_yesterday or had_nutra_yesterday) and not (has_workout_today or has_nutra_today):
                if self._send_once(
                    user,
                    token,
                    "streak_at_risk",
                    user_date,
                    "Streak at risk",
                    "Log your routine and nutrition today to protect your streak.",
                    {"event": "streak_at_risk"},
                ):
                    sent += 1

        self.stdout.write(self.style.SUCCESS(f"Sent {sent} runtime notifications."))
