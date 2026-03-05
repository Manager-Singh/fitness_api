from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    ProfileView,
    LogoutView,
    VerifyOTPView,
    SocialRegisterView,
    ResendOTPView,
    ForgotPasswordView,
    ResetPasswordView,
    ChangePasswordView
)

urlpatterns = [
    path('register', RegisterView.as_view(), name='register'),
    path('login', LoginView.as_view(), name='login'),
    path('profile', ProfileView.as_view(), name='profile'),
    path('logout', LogoutView.as_view(), name='logout'),
    path('verifyotp', VerifyOTPView.as_view(), name='verify_otp'),
    path('socialregister', SocialRegisterView.as_view(), name='socialregister'),
    path('resendotp', ResendOTPView.as_view(), name='resend_otp'),
    path('forgot-password', ForgotPasswordView.as_view()),
    path('reset-password', ResetPasswordView.as_view()),
    path('change-password', ChangePasswordView.as_view()),
]