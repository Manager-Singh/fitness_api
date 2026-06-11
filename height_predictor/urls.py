from django.urls import path

from .views import UltimateHeightPredictorView

urlpatterns = [
    path("ultimate-height", UltimateHeightPredictorView.as_view(), name="ultimate-height-predictor"),
]
