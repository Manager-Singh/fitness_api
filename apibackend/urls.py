"""
URL configuration for fitnessbackend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
import os
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from frontend.views import home
from apibackend.well_known_views import apple_app_site_association, assetlinks, invite_landing

urlpatterns = [
    path('admin', admin.site.urls),
    path('', home, name='home'),
    path('.well-known/apple-app-site-association', apple_app_site_association, name='apple_app_site_association'),
    path('.well-known/assetlinks.json', assetlinks, name='assetlinks'),
    path('invite', invite_landing, name='invite_landing'),
    path('invite/', invite_landing, name='invite_landing_slash'),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/', include('users.urls')),
    path('api/', include('user_profile.urls')),
    path('api/posture/', include('posture.urls')),
    # path('api/', include('wellness_tracker.urls')),
    # path('api/', include('exercise.urls')),
    path('api/', include('posture_questions.urls')),
    path("api/", include("workouts.urls")),
    path("api/", include("nutration.urls")),
    path("api/", include("apibackend.spec_urls")),
    path('api/posture/', include('posture.urls')),
    path("api/packages/", include("payment_packages.urls")),
    path("api/chatbot/", include("chatbot.urls")),
    path("api/test/", include("apibackend.test_seed_urls")),
    path('stumalitation', include('stumalitationdata.urls')),
]

# Serve MEDIA files only when DEBUG=True
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,      # <-- "/uploads/" (or whatever you set)
        document_root=settings.MEDIA_ROOT,   # <-- BASE_DIR / "uploads"
    )