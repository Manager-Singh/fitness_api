from django.urls import path
from . import views

urlpatterns = [
    path('/data', views.index, name='stumalitationdata_index'),
    path('/rollback/<int:user_id>/', views.rollback_user_logs, name='rollback_user_logs'),
]
