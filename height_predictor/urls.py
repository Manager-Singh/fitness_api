from django.urls import path

from .views import UltimateHeightAssessmentPrefillView, UltimateHeightPredictorView

urlpatterns = [
    path("ultimate-height", UltimateHeightPredictorView.as_view(), name="ultimate-height-predictor"),
    path("assessment-prefill", UltimateHeightAssessmentPrefillView.as_view(), name="ultimate-height-prefill"),
]
