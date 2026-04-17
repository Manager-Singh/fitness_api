# workouts/urls.py
from rest_framework.routers import DefaultRouter
from django.urls import path, include

from .views import ExerciseViewSet, AgeBracketViewSet, RoutineVariantViewSet
from .views_plan import MyWorkoutPlanView
from .views_log  import WorkoutLogViewSet
from .views_user_routine import UserRoutineListView
from .views_leaderboard import LeaderboardAPIView

router = DefaultRouter()
router.register("exercises",     ExerciseViewSet)
router.register("age-brackets",  AgeBracketViewSet)
router.register("routines",      RoutineVariantViewSet)
router.register("workout-logs",  WorkoutLogViewSet, basename="workout-log")

urlpatterns = [
    path("my-workouts", MyWorkoutPlanView.as_view(), name="my-workouts"),
    path("my-workouts/", MyWorkoutPlanView.as_view(), name="my-workouts-slash"),
    path("my-routine", UserRoutineListView.as_view(), name="my-routine"),
    path("my-routine/", UserRoutineListView.as_view(), name="my-routine-slash"),
    path("leaderboard", LeaderboardAPIView.as_view(), name="leaderboard"),
    path("leaderboard/", LeaderboardAPIView.as_view(), name="leaderboard-slash"),
    path("", include(router.urls)),
]
