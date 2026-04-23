# workouts/views_leaderboard.py
from django.db.models import Sum, Count
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta, timezone as dt_timezone
from utils.age import get_user_age
from utils.leaderboard import _current_validated_streak
from users.models import Friendship
from workouts.models import WorkoutEntry
from nutration.models_log import NutraEntry

import logging

logger = logging.getLogger(__name__)

from .serializers_leaderboard import LeaderboardResponseSerializer

User = get_user_model()

# class LeaderboardAPIView(APIView):
#     """
#     Returns leaderboard globally or filtered by routine_type.
#     Current user always included at the top, with rank info.
#     """
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         routine_type = request.query_params.get("routine_type")

#         # Base queryset: users with workout entries
#         qs = User.objects.filter(workout_sessions__entries__isnull=False)

#         if routine_type:
#             qs = qs.filter(workout_sessions__user_routine__routine_type=routine_type)

#         # Annotate with totals + global rank
#         qs = qs.annotate(
#             score=Sum("workout_sessions__entries__points"),
#             sessions_completed=Count("workout_sessions", distinct=True),
#             rank=Window(
#                 expression=Rank(),
#                 order_by=F("score").desc()
#             )
#         )

#         # Top 20 leaderboard
#         top_leaderboard = list(qs.order_by("-score")[:20])

#         # Current user entry (with rank)
#         try:
#             current_user_entry = qs.get(id=request.user.id)
#         except User.DoesNotExist:
#             current_user_entry = None

#         # If current user not in top 20, prepend them
#         if current_user_entry and current_user_entry not in top_leaderboard:
#             leaderboard = [current_user_entry] + top_leaderboard
#         else:
#             leaderboard = top_leaderboard

#         serializer = LeaderboardEntrySerializer(leaderboard, many=True)
#         return Response(serializer.data)


class LeaderboardAPIView(APIView):
    """
    Leaderboard filters:
    TODAY
    WEEK
    MONTH
    ALL
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        routine_type = request.query_params.get("routine_type")
        # Backward compatible aliases: period=today|week|month|all
        view_name = (request.query_params.get("view") or "").lower()
        period = (request.query_params.get("period") or "").lower()
        if not view_name:
            view_name = {
                "today": "alltime",
                "week": "weekly",
                "month": "weekly",
                "all": "alltime",
            }.get(period, "alltime")
        if view_name not in {"alltime", "weekly", "friends"}:
            return Response({"error": "view must be alltime|weekly|friends"}, status=400)
        page = max(int(request.query_params.get("page", 1)), 1)
        limit = min(max(int(request.query_params.get("limit", 50)), 1), 100)

        now = timezone.now()
        try:
            current_age = get_user_age(request.user)
        except Exception:
            current_age = 0
        current_is_adult = current_age >= 21

        qs = User.objects.filter(is_active=True)

        if routine_type:
            qs = qs.filter(
                workout_sessions__user_routine__routine_type=routine_type
            )

        # ---------- SCOPE FILTER ----------
        if view_name == "weekly":
            now_utc = timezone.now().astimezone(dt_timezone.utc)
            start = now_utc - timedelta(days=now_utc.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            qs = qs.filter(workout_sessions__entries__created_at__gte=start)
        elif view_name == "friends":
            accepted = Friendship.objects.filter(
                status=Friendship.STATUS_ACCEPTED,
            ).filter(
                user_id_a=request.user
            ) | Friendship.objects.filter(
                status=Friendship.STATUS_ACCEPTED,
                user_id_b=request.user
            )
            friend_ids = set()
            for rel in accepted:
                if rel.user_id_a_id == request.user.id:
                    friend_ids.add(rel.user_id_b_id)
                else:
                    friend_ids.add(rel.user_id_a_id)
            # Include current user row even with no friends.
            friend_ids.add(request.user.id)
            qs = qs.filter(id__in=friend_ids)

        # Build points scope using workout + nutrition/lifestyle logs.
        points_scope = {}
        user_ids = list(qs.values_list("id", flat=True))
        if view_name == "weekly":
            now_utc = timezone.now().astimezone(dt_timezone.utc)
            start = now_utc - timedelta(days=now_utc.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            w_rows = (
                WorkoutEntry.objects.filter(session__user_id__in=user_ids, created_at__gte=start)
                .values("session__user_id")
                .annotate(total=Sum("points"))
            )
            n_rows = (
                NutraEntry.objects.filter(session__user_id__in=user_ids, completed_at__gte=start)
                .values("session__user_id")
                .annotate(total=Sum("score"))
            )
        else:
            w_rows = (
                WorkoutEntry.objects.filter(session__user_id__in=user_ids)
                .values("session__user_id")
                .annotate(total=Sum("points"))
            )
            n_rows = (
                NutraEntry.objects.filter(session__user_id__in=user_ids)
                .values("session__user_id")
                .annotate(total=Sum("score"))
            )
        for r in w_rows:
            uid = r["session__user_id"]
            points_scope[uid] = int(points_scope.get(uid, 0) + (r["total"] or 0))
        for r in n_rows:
            uid = r["session__user_id"]
            points_scope[uid] = int(points_scope.get(uid, 0) + (r["total"] or 0))

        # Split by tier (adult/teen) and apply tie-break by streak length.
        tier_entries = []
        today_local = timezone.localdate()
        for u in qs:
            try:
                user_age = get_user_age(u)
            except Exception:
                logger.exception("Failed computing user_age for leaderboard", extra={"user_id": getattr(u, "id", None)})
                continue
            if (user_age >= 21) != current_is_adult:
                continue
            streak = _current_validated_streak(u, today_local)
            tier_entries.append(
                {
                    "user_id": u.id,
                    "display_name": (u.name or u.username or u.email or f"User {u.id}"),
                    "avatar_url": u.profile_image_url or None,
                    "points": int(points_scope.get(u.id, 0)),
                    "streak": streak,
                }
            )

        tier_entries.sort(key=lambda x: (-x["points"], -x["streak"], x["user_id"]))
        ranked = []
        prev_points = None
        rank = 0
        for idx, row in enumerate(tier_entries, start=1):
            if prev_points != row["points"]:
                rank = idx
                prev_points = row["points"]
            row["rank"] = rank
            row["is_current_user"] = row["user_id"] == request.user.id
            ranked.append(row)

        current_user_entry = next((r for r in ranked if r["user_id"] == request.user.id), None)
        current_user_rank = current_user_entry["rank"] if current_user_entry else (len(ranked) + 1)

        total = len(ranked)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        entries = ranked[start_idx:end_idx]

        payload = {
            "view": view_name,
            "tier": "adult" if current_is_adult else "teen",
            "current_user_rank": current_user_rank,
            "entries": entries,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
            },
        }
        serializer = LeaderboardResponseSerializer(payload)
        return Response(serializer.data)

# class LeaderboardAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def get(self, request):

#         demo_data = [
#             {"id": 21, "name": "Amit Sharma", "username": "amit.sharma@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 120, "sessions_completed": 15, "rank": 1},
#             {"id": 11, "name": "Rahul Verma", "username": "rahul.verma@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 115, "sessions_completed": 14, "rank": 2},
#             {"id": 34, "name": "Neha Gupta", "username": "neha.gupta@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 110, "sessions_completed": 13, "rank": 3},
#             {"id": 45, "name": "Pooja Mehta", "username": "pooja.mehta@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 105, "sessions_completed": 12, "rank": 4},
#             {"id": 67, "name": "Rohit Yadav", "username": "rohit.yadav@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 102, "sessions_completed": 12, "rank": 5},
#             {"id": 78, "name": "Anjali Singh", "username": "anjali.singh@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 98, "sessions_completed": 11, "rank": 6},
#             {"id": 89, "name": "Vikas Kumar", "username": "vikas.kumar@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 95, "sessions_completed": 11, "rank": 7},
#             {"id": 90, "name": "Sneha Patel", "username": "sneha.patel@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 92, "sessions_completed": 10, "rank": 8},
#             {"id": 91, "name": "Karan Malhotra", "username": "karan.malhotra@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 90, "sessions_completed": 10, "rank": 9},
#             {"id": 92, "name": "Deepak Chauhan", "username": "deepak.chauhan@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 87, "sessions_completed": 9, "rank": 10},
#             {"id": 93, "name": "Priya Arora", "username": "priya.arora@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 84, "sessions_completed": 9, "rank": 11},
#             {"id": 94, "name": "Suresh Nair", "username": "suresh.nair@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 80, "sessions_completed": 8, "rank": 12},
#             {"id": 95, "name": "Meena Iyer", "username": "meena.iyer@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 77, "sessions_completed": 8, "rank": 13},
#             {"id": 96, "name": "Tarun Bansal", "username": "tarun.bansal@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 74, "sessions_completed": 7, "rank": 14},
#             {"id": 97, "name": "Komal Jain", "username": "komal.jain@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 70, "sessions_completed": 7, "rank": 15},
#             {"id": 98, "name": "Nitin Agarwal", "username": "nitin.agarwal@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 66, "sessions_completed": 6, "rank": 16},
#             {"id": 99, "name": "Ritu Saxena", "username": "ritu.saxena@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 63, "sessions_completed": 6, "rank": 17},
#             {"id": 100, "name": "Arjun Thakur", "username": "arjun.thakur@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 60, "sessions_completed": 5, "rank": 18},
#             {"id": 101, "name": "Shalini Kapoor", "username": "shalini.kapoor@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 55, "sessions_completed": 5, "rank": 19},
#             {"id": 102, "name": "Mohit Saini", "username": "mohit.saini@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 52, "sessions_completed": 4, "rank": 20}
#         ]


#         return Response(demo_data)