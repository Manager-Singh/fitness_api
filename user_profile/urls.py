from django.urls import path
from . import views

urlpatterns = [
    path('update-profile-old', views.update_profile_users_old, name='update_profile_old'),
    path('update-profile', views.update_profile_users, name='update_profile'),
    path('create-payment-intent', views.create_payment_intent, name='create_payment_intent'),
    path('save-payment-intent', views.save_payment_intent, name='save_payment_intent'),
    path('get-report', views.get_report, name='get_report'),
    path('get-profile', views.get_profile, name='get_profile'),
    path('subscribe/free', views.subscribe_free_plan, name='subscribe_free_plan'),
]