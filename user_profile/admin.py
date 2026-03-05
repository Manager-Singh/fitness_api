from django.contrib import admin
from user_profile.models import UserProfile
from users.models import User

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profile'

class CustomUserAdmin(admin.ModelAdmin):
    inlines = (UserProfileInline,)

# Unregister the default User admin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)