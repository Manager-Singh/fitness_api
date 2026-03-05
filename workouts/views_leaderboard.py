# workouts/views_leaderboard.py
from django.db.models import Sum, Count, Window, F
from django.db.models.functions import Rank
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model

from .serializers_leaderboard import LeaderboardEntrySerializer

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
    permission_classes = [IsAuthenticated]

    def get(self, request):

        demo_data = [
            {"id": 21, "name": "Amit Sharma", "username": "amit.sharma@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 120, "sessions_completed": 15, "rank": 1},
            {"id": 11, "name": "Rahul Verma", "username": "rahul.verma@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 115, "sessions_completed": 14, "rank": 2},
            {"id": 34, "name": "Neha Gupta", "username": "neha.gupta@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 110, "sessions_completed": 13, "rank": 3},
            {"id": 45, "name": "Pooja Mehta", "username": "pooja.mehta@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 105, "sessions_completed": 12, "rank": 4},
            {"id": 67, "name": "Rohit Yadav", "username": "rohit.yadav@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 102, "sessions_completed": 12, "rank": 5},
            {"id": 78, "name": "Anjali Singh", "username": "anjali.singh@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 98, "sessions_completed": 11, "rank": 6},
            {"id": 89, "name": "Vikas Kumar", "username": "vikas.kumar@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 95, "sessions_completed": 11, "rank": 7},
            {"id": 90, "name": "Sneha Patel", "username": "sneha.patel@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 92, "sessions_completed": 10, "rank": 8},
            {"id": 91, "name": "Karan Malhotra", "username": "karan.malhotra@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 90, "sessions_completed": 10, "rank": 9},
            {"id": 92, "name": "Deepak Chauhan", "username": "deepak.chauhan@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 87, "sessions_completed": 9, "rank": 10},
            {"id": 93, "name": "Priya Arora", "username": "priya.arora@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 84, "sessions_completed": 9, "rank": 11},
            {"id": 94, "name": "Suresh Nair", "username": "suresh.nair@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 80, "sessions_completed": 8, "rank": 12},
            {"id": 95, "name": "Meena Iyer", "username": "meena.iyer@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 77, "sessions_completed": 8, "rank": 13},
            {"id": 96, "name": "Tarun Bansal", "username": "tarun.bansal@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 74, "sessions_completed": 7, "rank": 14},
            {"id": 97, "name": "Komal Jain", "username": "komal.jain@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 70, "sessions_completed": 7, "rank": 15},
            {"id": 98, "name": "Nitin Agarwal", "username": "nitin.agarwal@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 66, "sessions_completed": 6, "rank": 16},
            {"id": 99, "name": "Ritu Saxena", "username": "ritu.saxena@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 63, "sessions_completed": 6, "rank": 17},
            {"id": 100, "name": "Arjun Thakur", "username": "arjun.thakur@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 60, "sessions_completed": 5, "rank": 18},
            {"id": 101, "name": "Shalini Kapoor", "username": "shalini.kapoor@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 55, "sessions_completed": 5, "rank": 19},
            {"id": 102, "name": "Mohit Saini", "username": "mohit.saini@gmail.com", "profile_image_url":"https://i.pravatar.cc/150?img=1", "score": 52, "sessions_completed": 4, "rank": 20}
        ]


        return Response(demo_data)