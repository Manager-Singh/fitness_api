from django.contrib import admin
from django.conf import settings
from django.utils.html import format_html
from .models import ExerciseItem, ExerciseSubmission

@admin.register(ExerciseItem)
class ExerciseItemAdmin(admin.ModelAdmin):
    list_filter = ('category', 'age_group')
    list_display = ('title', 'category', 'age_group', 'points', 'image_tag')  # <-- image_tag not image
    readonly_fields = ('image_tag',)  # <-- image_tag

    def image_tag(self, obj):
        if obj.image:
            full_url = f"/uploads/{obj.image.name.split('uploads/',1)[-1]}"
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" width="80" height="80" style="object-fit: cover; border-radius: 8px;" />'
                '</a>',
                full_url,
                full_url
            )
        return "No Image"

    image_tag.short_description = 'Image Preview'  # Column label


admin.site.register(ExerciseSubmission)  # Keep this for ExerciseSubmission
