# from datetime import timedelta
# from django.contrib.auth import get_user_model
# from django.db.models import Sum, Count, Window, F, Value
# from django.db.models.functions import Rank, Coalesce
# from django.core.cache import cache
# from django.utils import timezone

# User = get_user_model()

# CACHE_TTL = 60 * 10  # 10 minutes


# def _leaderboard_qs(routine_type=None, until_date=None):
#     """
#     Base leaderboard queryset.
#     - TOTAL rank if until_date is None
#     - Historical rank if until_date is provided
#     """

#     qs = User.objects.filter(
#         workout_sessions__entries__isnull=False
#     )

#     if routine_type:
#         qs = qs.filter(
#             workout_sessions__user_routine__routine_type=routine_type
#         )

#     if until_date:
#         qs = qs.filter(
#             workout_sessions__date__lte=until_date
#         )

#     qs = qs.annotate(
#         total_score=Coalesce(
#             Sum("workout_sessions__entries__points"),
#             Value(0)
#         ),
#         sessions_completed=Count("workout_sessions", distinct=True),
#     )

#     qs = qs.annotate(
#         total_rank=Window(
#             expression=Rank(),
#             order_by=F("total_score").desc()
#         )
#     )

#     return qs


# def get_user_leaderboard_rank(user, routine_type=None):
#     """
#     Returns:
#     - total rank
#     - total score
#     - yesterday rank
#     - rank change
#     """

#     today = timezone.localdate()
#     yesterday = today - timedelta(days=1)

#     cache_key = f"leaderboard:total:{user.id}:{routine_type or 'all'}"
#     cached = cache.get(cache_key)

#     if cached:
#         return cached

#     # ─────────────────────────────
#     # TOTAL RANK
#     # ─────────────────────────────
#     qs = _leaderboard_qs(routine_type)

#     total_entry = qs.filter(id=user.id).first()

#     if total_entry:
#         total_rank = total_entry.total_rank
#         total_score = total_entry.total_score
#         sessions_completed = total_entry.sessions_completed
#     else:
#         total_rank = None
#         total_score = 0
#         sessions_completed = 0

#     # ─────────────────────────────
#     # YESTERDAY RANK
#     # ─────────────────────────────
#     yesterday_qs = _leaderboard_qs(
#         routine_type,
#         until_date=yesterday
#     )

#     yesterday_entry = yesterday_qs.filter(id=user.id).first()

#     if yesterday_entry:
#         yesterday_rank = yesterday_entry.total_rank
#     else:
#         yesterday_rank = None

#     # ─────────────────────────────
#     # RANK CHANGE
#     # ─────────────────────────────
#     rank_change = None
#     direction = "same"

#     if total_rank and yesterday_rank:
#         rank_change = yesterday_rank - total_rank

#         if rank_change > 0:
#             direction = "up"
#         elif rank_change < 0:
#             direction = "down"

#     elif total_rank and not yesterday_rank:
#         direction = "new"

#     data = {
#         "total_rank": total_rank or 0,
#         "my_rank": total_rank or 0,
#         "total_score": total_score or 0,
#         "yesterday_rank": yesterday_rank or 0,
#         "rank_change": rank_change or 0,
#         "direction": direction,
#         "sessions_completed": sessions_completed or 0,
#     }

#     cache.set(cache_key, data, CACHE_TTL)

#     return data

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count
from django.core.cache import cache
from nutration.models_log import NutraEntry
from workouts.models import WorkoutEntry, WorkoutSession, Tier, RoutineType
from utils.age import get_user_age
from users.models import DailyLog
from utils.user_time import user_today

import logging

logger = logging.getLogger(__name__)

User = get_user_model()

# Keep rankings responsive; leaderboard points are recomputed frequently.
CACHE_TTL = 30  # seconds


def _is_valid_streak_day(user, day, age):
    def core_done(routine_type):
        assigned_core = set(
            WorkoutSession.objects.filter(
                user=user,
                date=day,
                user_routine__routine_type=routine_type,
                user_routine__is_active=True,
                user_routine__exercises__tier=Tier.CORE,
            ).values_list("user_routine__exercises__id", flat=True)
        )
        if not assigned_core:
            return False
        done_core = set(
            WorkoutEntry.objects.filter(
                session__user=user,
                session__date=day,
                session__user_routine__routine_type=routine_type,
                user_routine_exercise__tier=Tier.CORE,
            ).values_list("user_routine_exercise_id", flat=True)
        )
        return assigned_core.issubset(done_core)

    if age >= 21:
        foods = NutraEntry.objects.filter(
            session__user=user,
            session__date=day,
            food__isnull=False,
        ).select_related("module")
        has_disc = False
        has_muscle = False
        for entry in foods:
            name = ((entry.module.name if entry.module else "") or "").lower()
            if any(k in name for k in ("disc", "lubric", "spine")):
                has_disc = True
            if any(k in name for k in ("muscle", "repair", "fuel")):
                has_muscle = True
        return core_done(RoutineType.POSTURE) and has_disc and has_muscle

    teen_food_ok = NutraEntry.objects.filter(
        session__user=user,
        session__date=day,
        food__isnull=False,
    ).exists()
    return core_done(RoutineType.POSTURE) and core_done(RoutineType.HGH) and teen_food_ok


def _current_validated_streak(user, today):
    try:
        age = get_user_age(user)
    except Exception:
        logger.exception("Failed computing user age for streak", extra={"user_id": getattr(user, "id", None)})
        age = 0
    streak = 0
    day = today
    while _is_valid_streak_day(user, day, age):
        streak += 1
        day -= timedelta(days=1)
    return streak


def _same_tier_users(base_user):
    user_ids = []
    try:
        base_age = get_user_age(base_user)
    except Exception:
        logger.exception("Failed computing base user age for tier match", extra={"user_id": getattr(base_user, "id", None)})
        base_age = 0
    want_adult = base_age >= 21
    for candidate in User.objects.filter(is_active=True):
        try:
            age = get_user_age(candidate)
        except Exception:
            logger.exception("Failed computing candidate age for tier match", extra={"user_id": getattr(candidate, "id", None)})
            continue
        if (age >= 21) == want_adult:
            user_ids.append(candidate.id)
    return user_ids


def _build_rank_map(user_ids, until_date=None, routine_type=None):
    """
    Spec alignment: rank by "traceable" engine-counting points, not raw diary sums.
    We use DailyLog.engine1_points + DailyLog.engine2_points which already applies
    routing, gates, and daily caps (e.g., teen nutrition max 35, adult nutrition max 12).
    """
    daily_filter = {"user_id__in": user_ids}
    if until_date:
        daily_filter["log_date__lte"] = until_date

    # Routine-specific leaderboard (if requested):
    # - posture: engine1 only
    # - hgh: engine2 only (teens); adults naturally return 0
    rt = (routine_type or "").lower()
    if rt == "posture":
        points_rows = DailyLog.objects.filter(**daily_filter).values("user_id").annotate(
            e1=Sum("engine1_points")
        )
    elif rt == "hgh":
        points_rows = DailyLog.objects.filter(**daily_filter).values("user_id").annotate(
            e2=Sum("engine2_points")
        )
    else:
        points_rows = DailyLog.objects.filter(**daily_filter).values("user_id").annotate(
            e1=Sum("engine1_points"),
            e2=Sum("engine2_points"),
        )
    sessions_completed = WorkoutSession.objects.filter(user_id__in=user_ids).values("user_id").annotate(
        total=Count("id", distinct=True)
    )

    totals = {uid: {"points": 0, "streak": 0, "sessions": 0} for uid in user_ids}
    for row in points_rows:
        totals[row["user_id"]]["points"] += int((row.get("e1") or 0) + (row.get("e2") or 0))
    for row in sessions_completed:
        totals[row["user_id"]]["sessions"] = row["total"] or 0

    for uid in user_ids:
        user_obj = User.objects.filter(id=uid).first()
        if not user_obj:
            totals[uid]["streak"] = 0
            continue
        # Historical rank snapshots anchor streaks to ``until_date``; live totals use each user's local "today".
        streak_anchor = until_date if until_date else user_today(user_obj)
        totals[uid]["streak"] = _current_validated_streak(user_obj, streak_anchor)

    ordered = sorted(
        totals.items(),
        key=lambda kv: (-kv[1]["points"], -kv[1]["streak"], kv[0]),
    )
    rank_map = {}
    prev_points = None
    rank = 0
    for idx, (uid, data) in enumerate(ordered, start=1):
        if prev_points != data["points"]:
            rank = idx
            prev_points = data["points"]
        rank_map[uid] = {
            "rank": rank,
            "points": data["points"],
            "streak": data["streak"],
            "sessions": data["sessions"],
            "total_users": len(user_ids),
        }
    return rank_map


def get_user_leaderboard_rank(user, subscription_data, routine_type=None):
    """
    Returns:
    - total rank
    - total score
    - yesterday rank
    - rank change
    """

    today = user_today(user)
    yesterday = today - timedelta(days=1)

    cache_key = f"leaderboard:total:{user.id}:{routine_type or 'all'}"
    cached = cache.get(cache_key)

    if cached:
        return cached

    tier_user_ids = _same_tier_users(user)
    total_map = _build_rank_map(tier_user_ids, until_date=None, routine_type=routine_type)
    yesterday_map = _build_rank_map(tier_user_ids, until_date=yesterday, routine_type=routine_type)

    current = total_map.get(user.id)
    if current:
        total_rank = current["rank"]
        total_score = current["points"]
        sessions_completed = current["sessions"]
    else:
        total_rank = len(tier_user_ids) + 1
        total_score = 0
        sessions_completed = 0

    yesterday_entry = yesterday_map.get(user.id)
    yesterday_rank = yesterday_entry["rank"] if yesterday_entry else None

    # ─────────────────────────────
    # RANK CHANGE
    # ─────────────────────────────
    rank_change = None
    direction = "same"

    if total_rank and yesterday_rank:
        rank_change = yesterday_rank - total_rank

        if rank_change > 0:
            direction = "up"
        elif rank_change < 0:
            direction = "down"

    elif total_rank and not yesterday_rank:
        direction = "new"
    data = {
        "total_rank": total_rank or 0,
        "my_rank": total_rank or 0,
        "total_score": total_score or 0,
        "yesterday_rank": yesterday_rank or 0,
        "rank_change": rank_change or 0,
        "direction": direction,
        "sessions_completed": sessions_completed or 0,
        "streak": (current or {}).get("streak", 0),
        "tier_total_users": len(tier_user_ids),
    }

    cache.set(cache_key, data, CACHE_TTL)

    return data