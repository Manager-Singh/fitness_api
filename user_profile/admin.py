"""
Admin for user_profile app.

IMPORTANT: Do not register/unregister the User model here. The canonical User admin
is defined in `users/admin.py` to avoid multiple apps fighting over User registration.
"""

from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "gender", "age", "birth_date", "last_scan")
    search_fields = ("user__email", "user__username")
    list_filter = ("gender",)