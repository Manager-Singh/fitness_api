from django.urls import path
from rest_framework.routers import SimpleRouter

from habits.views import HabitCatalogView, HabitLogViewSet

router = SimpleRouter(trailing_slash=False)
router.register("habit-logs", HabitLogViewSet, basename="habit-log")

urlpatterns = [
    path("habits", HabitCatalogView.as_view(), name="habits-catalog"),
    *router.urls,
]
