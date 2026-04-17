from django.urls import path

from .test_seed_views import SeedDayDataAPIView


urlpatterns = [
    path("seed-day", SeedDayDataAPIView.as_view(), name="test-seed-day"),
]

