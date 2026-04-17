from django.urls import path
from .views import FullPostureAnalysisAPIView, ScanAPIView, MockScanAPIView  #PostureImageUploadView

urlpatterns = [
    # path('upload', PostureImageUploadView.as_view(), name='posture-upload'),
    path('full-posture-analysis', FullPostureAnalysisAPIView.as_view(), name='posture-analysis'),
    path('scan', ScanAPIView.as_view(), name='scan'),
    path('scan/mock', MockScanAPIView.as_view(), name='scan-mock'),
]