# wellness/urls.py

from django.urls import path
from .views import WellnessItemListView, WellnessSubmissionCreateView

urlpatterns = [
    path('wellness-items', WellnessItemListView.as_view(), name='wellness-items'),
    path('wellness-submission', WellnessSubmissionCreateView.as_view(), name='wellness-submission'),
]
