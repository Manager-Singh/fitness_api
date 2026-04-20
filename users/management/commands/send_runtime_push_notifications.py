from django.core.management.base import BaseCommand
from django.utils import timezone

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
    def _minutes_since_midnight(dt):
        return int(dt.hour) * 60 + int(dt.minute)

    @classmethod
    def _within_local_time_window(cls, local_now, target_hhmm, window_minutes=15):
        """
        Cron-safe local-time match.

        Instead of requiring an exact (hour, minute) match, treat a trigger as
        "eligible" when the current local time is within +/- window_minutes of
        the target time, using circular distance across midnight.
        """
        target_h, target_m = target_hhmm
        now_m = cls._minutes_since_midnight(local_now)
        target_mins = int(target_h) * 60 + int(target_m)
        diff = abs(now_m - target_mins)
        diff = min(diff, 1440 - diff)
        return diff <= int(window_minutes)

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
        users, _today = users_for_notifications(now=now)
        sent = 0
        for user in users:
            local_now = user_now(user)
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

            is_paid = bool(sub.get("is_paid"))
            is_trial = bool(sub.get("is_trial"))
            trial_day = sub.get("trial_day")

            # Section 12.2 — "First open after age transition"
            # In this codebase, "first open" is proxied by the moment we set
            # user.transitioned_to_adult_at in the dashboard flow.
            transitioned_at = getattr(user, "transitioned_to_adult_at", None)
            if transitioned_at is not None:
                try:
                    transitioned_local_date = transitioned_at.astimezone(local_now.tzinfo).date()
                except Exception:
                    transitioned_local_date = transitioned_at.date()
                if transitioned_local_date == user_date:
                    if self._send_once(
                        user,
                        token,
                        "age_transition_first_open",
                        user_date,
                        "Adult mode unlocked",
                        "You’ve entered adult mode! Take your first scan to unlock your recovery plan.",
                        {"event": "age_transition_first_open"},
                    ):
                        sent += 1

            # Section 12.2 — Trial expiry warning (teens) Day 6 at 09:00 local time
            if age < 21 and is_trial and trial_day == 6 and self._within_local_time_window(local_now, (9, 0), window_minutes=15):
                if self._send_once(
                    user,
                    token,
                    "trial_day6_warning",
                    user_date,
                    "Trial ending soon",
                    "1 day left on your free trial. Keep your height growing — unlock full access.",
                    {"event": "trial_day6_warning"},
                ):
                    sent += 1

            # Section 12.2 — Trial expired (teens) Day 7 at 23:59 local time
            if (
                age < 21
                and (not is_paid)
                and trial_day
                and int(trial_day) >= 7
                and self._within_local_time_window(local_now, (23, 59), window_minutes=15)
            ):
                if self._send_once(
                    user,
                    token,
                    "trial_expired",
                    user_date,
                    "Trial ended",
                    "Your GrowthMax+ gains have paused. Upgrade to keep seeing your height grow.",
                    {"event": "trial_expired"},
                ):
                    sent += 1

            # Section 12.2 — Re-scan timer expired (adults) at 00:00 on expiry day
            # Section 12.2 — Re-scan timer expired (teens, paid) at 00:00 on expiry day
            if profile.last_scan:
                days_since_scan = (user_date - profile.last_scan.date()).days
                if days_since_scan >= 7 and self._within_local_time_window(local_now, (0, 0), window_minutes=15):
                    if age >= 21:
                        if self._send_once(
                            user,
                            token,
                            "rescan_ready_adult",
                            user_date,
                            "Re-scan ready",
                            "Your 7-day re-scan is ready. See how much you’ve recovered.",
                            {"event": "rescan_ready", "tier": "adult", "days_since_scan": str(days_since_scan)},
                        ):
                            sent += 1
                    else:
                        # Spec only calls out the teen re-scan expiry notification for paid teens.
                        if is_paid:
                            if self._send_once(
                                user,
                                token,
                                "rescan_ready_teen_paid",
                                user_date,
                                "Re-scan ready",
                                "Time for your weekly re-scan. Check your posture progress.",
                                {"event": "rescan_ready", "tier": "teen", "days_since_scan": str(days_since_scan)},
                            ):
                                sent += 1

            # Section 12.2 — Streak at risk — routine not completed
            # Spec condition: "if no exercise logged that day" at 21:00 local time.
            has_workout_today = WorkoutEntry.objects.filter(session__user=user, session__date=user_date).exists()
            if self._within_local_time_window(local_now, (21, 0), window_minutes=15) and not has_workout_today:
                if self._send_once(
                    user,
                    token,
                    "streak_at_risk",
                    user_date,
                    "Streak at risk",
                    "Your streak is at risk! Log at least one exercise before midnight to keep it alive.",
                    {"event": "streak_at_risk"},
                ):
                    sent += 1

        self.stdout.write(self.style.SUCCESS(f"Sent {sent} runtime notifications."))
