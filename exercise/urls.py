# Exercise/urls.py

from django.urls import path
from .views import ExerciseItemListView, ExerciseSubmissionCreateView

urlpatterns = [
    path('exercise-items', ExerciseItemListView.as_view(), name='exercise-items'),
    path('exercise-submission', ExerciseSubmissionCreateView.as_view(), name='exercise-submission'),
]
