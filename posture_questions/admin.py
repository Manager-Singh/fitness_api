from django.contrib import admin
from posture_questions.models import PostureQuestion
from users.models import User


class PostureQuestionInline(admin.StackedInline):
    model = PostureQuestion
    can_delete = False
    verbose_name_plural = "User Profile"


class CustomUserAdmin(admin.ModelAdmin):
    inlines = (PostureQuestionInline,)


# Unregister the default User admin
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, CustomUserAdmin)