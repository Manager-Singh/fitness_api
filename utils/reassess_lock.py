from __future__ import annotations

from workouts.models import WorkoutEntry
from utils.user_time import user_today


REASSESS_BLOCKED_MESSAGE = (
    "You've already started today's routine. Re-assess tomorrow - before starting any workouts - "
    "for an accurate reading and updated plan."
)


def workouts_logged_today(user) -> int:
    today = user_today(user)
    return int(
        WorkoutEntry.objects.filter(
            session__user=user,
            session__date=today,
        ).count()
    )


def reassess_lock_status(user) -> dict:
    count = workouts_logged_today(user)
    can_reassess = count == 0
    return {
        "can_reassess": can_reassess,
        "workouts_logged_today": count,
        "reassess_message": "" if can_reassess else REASSESS_BLOCKED_MESSAGE,
    }


def reassess_block_response(user) -> tuple[dict | None, int | None]:
    status = reassess_lock_status(user)
    if status["can_reassess"]:
        return None, None
    return {
        "error": "reassess_locked_after_workout",
        "message": REASSESS_BLOCKED_MESSAGE,
        **status,
    }, 423
