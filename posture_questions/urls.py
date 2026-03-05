from django.urls import path
from . import views

urlpatterns = [
    path('update-posture-questions', views.upsert_posture_questions, name='update_posture_questions'),
    path('dashboard', views.get_posture_questions, name='get_posture_questions'),
    
]