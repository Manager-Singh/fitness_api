"""
Admin for posture_questions app.

IMPORTANT: Do not register/unregister the User model here. The canonical User admin
is defined in `users/admin.py` to avoid multiple apps fighting over User registration.
"""

from django.contrib import admin

from .models import PostureQuestion


@admin.register(PostureQuestion)
class PostureQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "user")
    search_fields = ("user__email", "user__username")