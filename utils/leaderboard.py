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
from django.db.models import Sum, Count, Window, F, Value
from django.db.models.functions import Rank, Coalesce
from django.core.cache import cache
from django.utils import timezone

User = get_user_model()

CACHE_TTL = 60 * 10  # 10 minutes


def _leaderboard_qs(routine_type=None, until_date=None):
    """
    Base leaderboard queryset.
    - TOTAL rank if until_date is None
    - Historical rank if until_date is provided
    """

    qs = User.objects.filter(
        workout_sessions__entries__isnull=False
    )

    if routine_type:
        qs = qs.filter(
            workout_sessions__user_routine__routine_type=routine_type
        )

    if until_date:
        qs = qs.filter(
            workout_sessions__date__lte=until_date
        )

    qs = qs.annotate(
        total_score=Coalesce(
            Sum("workout_sessions__entries__points"),
            Value(0)
        ),
        sessions_completed=Count("workout_sessions", distinct=True),
    )

    qs = qs.annotate(
        total_rank=Window(
            expression=Rank(),
            order_by=F("total_score").desc()
        )
    )

    return qs


def get_user_leaderboard_rank(user, routine_type=None):
    """
    Returns:
    - total rank
    - total score
    - yesterday rank
    - rank change
    """

    today = timezone.localdate()
    yesterday = today - timedelta(days=1)

    cache_key = f"leaderboard:total:{user.id}:{routine_type or 'all'}"
    cached = cache.get(cache_key)

    if cached:
        return cached

    # ─────────────────────────────
    # TOTAL RANK
    # ─────────────────────────────
    qs = _leaderboard_qs(routine_type)

    total_entry = qs.filter(id=user.id).first()

    if total_entry:
        total_rank = total_entry.total_rank
        total_score = total_entry.total_score
        sessions_completed = total_entry.sessions_completed
    else:
        total_rank = None
        total_score = 0
        sessions_completed = 0

    # ─────────────────────────────
    # YESTERDAY RANK
    # ─────────────────────────────
    yesterday_qs = _leaderboard_qs(
        routine_type,
        until_date=yesterday
    )

    yesterday_entry = yesterday_qs.filter(id=user.id).first()

    if yesterday_entry:
        yesterday_rank = yesterday_entry.total_rank
    else:
        yesterday_rank = None

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
    }

    cache.set(cache_key, data, CACHE_TTL)

    return data