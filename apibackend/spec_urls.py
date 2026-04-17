from django.urls import path

# Spec/runtime endpoints are optional. This module exists so that the main URLConf
# can safely include it in all environments without failing import checks.

urlpatterns = [
    # Intentionally empty by default.
]

from django.urls import path

from .spec_views import (
    LogExerciseAPIView,
    LogFoodAPIView,
    LogLifestyleAPIView,
    UserStateAPIView,
)


urlpatterns = [
    path("log/exercise", LogExerciseAPIView.as_view()),
    path("log/food", LogFoodAPIView.as_view()),
    path("log/lifestyle", LogLifestyleAPIView.as_view()),
    path("user/state", UserStateAPIView.as_view()),
]
