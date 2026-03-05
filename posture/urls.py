from django.urls import path
from .views import FullPostureAnalysisAPIView  #PostureImageUploadView

urlpatterns = [
    # path('upload', PostureImageUploadView.as_view(), name='posture-upload'),
    path('full-posture-analysis', FullPostureAnalysisAPIView.as_view(), name='posture-analysis'),
    
]