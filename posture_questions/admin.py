from django.contrib import admin
from posture_questions.models import PostureQuestion
from users.models import User

class PostureQuestionInline(admin.StackedInline):
    model = PostureQuestion
    can_delete = False
    verbose_name_plural = 'User Profile'

class CustomUserAdmin(admin.ModelAdmin):
    inlines = (PostureQuestionInline,)

# Unregister the default User admin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)