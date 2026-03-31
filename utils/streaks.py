from datetime import timedelta
from django.utils import timezone
from nutration.models_log import NutraSession
from workouts.models import WorkoutSession
from .leaderboard import get_user_leaderboard_rank


def get_user_streaks(user,subscription_data):
    """
    Returns all streak-related data in one call.
    """

    today = timezone.localdate()

    # ─────────────────────────────────────────────
    # Fetch dates ONCE
    # ─────────────────────────────────────────────
    nutra_dates = list(
        NutraSession.objects
        .filter(user=user)
        .values_list("date", flat=True)
        .distinct()
        .order_by("date")
    )

    workout_dates = list(
        WorkoutSession.objects
        .filter(user=user)
        .values_list("date", flat=True)
        .distinct()
        .order_by("date")
    )

    nutra_set = set(nutra_dates)
    workout_set = set(workout_dates)

    # ─────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────
    def current_streak(dates_set):
        streak = 0
        day = today
        while day in dates_set:
            streak += 1
            day -= timedelta(days=1)
        return streak

    # def longest_streak(dates):
    #     if not dates:
    #         return 0
    #     longest = current = 1
    #     for i in range(1, len(dates)):
    #         if dates[i] == dates[i - 1] + timedelta(days=1):
    #             current += 1
    #             longest = max(longest, current)
    #         else:
    #             current = 1
    #     return longest

    # ─────────────────────────────────────────────
    # Calculate streaks
    # ─────────────────────────────────────────────
    nutrition_streak = current_streak(nutra_set)
    workout_streak = current_streak(workout_set)

    health_streak = 0
    day = today
    while day in nutra_set and day in workout_set:
        health_streak += 1
        day -= timedelta(days=1)

    # ─────────────────────────────────────────────
    # Final payload
    # ─────────────────────────────────────────────

    leaderboard_data = get_user_leaderboard_rank(
        user,
        subscription_data,
        routine_type=None   # or "POSTURE" / "HGH" if needed
    )
    return {
        "nutrition": {
            "today": today in nutra_set,
            "current_streak": nutrition_streak,
            # "longest_streak": longest_streak(nutra_dates),
        },
        "workout": {
            "today": today in workout_set,
            "current_streak": workout_streak,
            # "longest_streak": longest_streak(workout_dates),
        },
        "health": {
            "current_streak": health_streak,
        },
        "leaderboard": leaderboard_data,
    }
