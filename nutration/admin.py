# from django.contrib import admin
# from django.utils.safestring import mark_safe

# from .models import (
#     AgeGroup, Module,
#     Food, ModuleFood,
#     Activity, ModuleActivity
# )


# # ──────────────────────────
# # helper: tiny thumbnail html
# # ──────────────────────────
# def _thumb(image_field, size=60):
#     if not image_field:
#         return "—"
#     return mark_safe(
#         f'<img src="{image_field.url}" '
#         f'style="height:{size}px;width:{size}px;object-fit:cover;border-radius:4px;" />'
#     )


# # ─── inline helpers ───
# class ModuleFoodInline(admin.TabularInline):
#     model  = ModuleFood
#     extra  = 1
#     autocomplete_fields = ("food",)
#     fields = ("preview", "food", "score", "serving_size")
#     readonly_fields = ("preview",)

#     # preview column
#     def preview(self, obj):
#         return _thumb(obj.food.image)
#     preview.short_description = ""


# class ModuleActivityInline(admin.TabularInline):
#     model  = ModuleActivity
#     extra  = 1
#     autocomplete_fields = ("activity",)
#     fields = ("preview", "activity", "score", "recommendation")
#     readonly_fields = ("preview",)

#     def preview(self, obj):
#         return _thumb(obj.activity.image)
#     preview.short_description = ""


# # ─── master tables ───
# @admin.register(Food)
# class FoodAdmin(admin.ModelAdmin):
#     list_display  = ("name","short_name", "thumb", "calories", "protein")
#     search_fields = ("name",)
#     readonly_fields = ("thumb",)

#     def thumb(self, obj):
#         return _thumb(obj.image, size=70)
#     thumb.short_description = ""   # no column title


# @admin.register(Activity)
# class ActivityAdmin(admin.ModelAdmin):
#     list_display  = ("name","short_name", "thumb", "default_duration")
#     search_fields = ("name",)
#     readonly_fields = ("thumb",)

#     def thumb(self, obj):
#         return _thumb(obj.image, size=70)
#     thumb.short_description = ""


# @admin.register(AgeGroup)
# class AgeGroupAdmin(admin.ModelAdmin):
#     list_display = ("name", "min_age", "max_age_display")
#     ordering     = ("min_age",)

#     def max_age_display(self, obj):
#         return obj.max_age if obj.max_age is not None else "∞"
#     max_age_display.short_description = "Max age"


# # ─── dynamic inline for Module ───
# @admin.register(Module)
# class ModuleAdmin(admin.ModelAdmin):
#     list_display  = ("name", "type", "age_group")
#     list_filter   = ("type", "age_group")
#     search_fields = ("name",)

#     def get_inline_instances(self, request, obj=None):
#         # ----- add form -----
#         if obj is None:
#             initial_type = request.GET.get("type")
#             if initial_type == Module.NUTRITION:
#                 cls = ModuleFoodInline
#             elif initial_type == Module.LIFESTYLE:
#                 cls = ModuleActivityInline
#             else:
#                 return []
#             return [cls(self.model, self.admin_site)]

#         # ----- change form -----
#         cls = ModuleFoodInline if obj.type == Module.NUTRITION else ModuleActivityInline
#         return [cls(self.model, self.admin_site)]

from django.contrib import admin
from django.utils.safestring import mark_safe

from .models import (
    AgeGroup, Module,
    Food, ModuleFood,
    Activity, ModuleActivity
)


# ──────────────────────────
# helper: tiny thumbnail html
# ──────────────────────────
def _thumb(image_field, size=60):
    if not image_field:
        return "—"
    return mark_safe(
        f'<img src="{image_field.url}" '
        f'style="height:{size}px;width:{size}px;object-fit:cover;border-radius:4px;" />'
    )


# ──────────────────────────
# helper: audio/video preview
# ──────────────────────────
def _media_preview(file_field):
    if not file_field:
        return "—"

    url = file_field.url
    ext = url.split(".")[-1].lower()

    # audio preview
    if ext in ["mp3", "wav", "aac", "m4a", "ogg"]:
        return mark_safe(
            f'<audio controls style="height:40px; width:160px;">'
            f'<source src="{url}">'
            f'</audio>'
        )

    # video preview
    if ext in ["mp4", "mov", "avi", "mkv", "webm"]:
        return mark_safe(
            f'<video width="180" height="120" controls>'
            f'<source src="{url}">'
            f'</video>'
        )

    return "Preview not supported"


# ─── inline helpers ───
class ModuleFoodInline(admin.TabularInline):
    model  = ModuleFood
    extra  = 1
    autocomplete_fields = ("food",)
    fields = ("preview", "food", "score", "serving_size")
    readonly_fields = ("preview",)

    def preview(self, obj):
        return _thumb(obj.food.image)
    preview.short_description = ""


class ModuleActivityInline(admin.TabularInline):
    model  = ModuleActivity
    extra  = 1
    autocomplete_fields = ("activity",)
    fields = (
        "preview",
        "activity",
        "score",
        "recommendation",
        "audio",
        "audio_preview",
        "video",
        "video_preview",
    )
    readonly_fields = ("preview", "audio_preview", "video_preview")

    def preview(self, obj):
        return _thumb(obj.activity.image)
    preview.short_description = ""

    def audio_preview(self, obj):
        return _media_preview(obj.audio)
    audio_preview.short_description = "Audio"

    def video_preview(self, obj):
        return _media_preview(obj.video)
    video_preview.short_description = "Video"


# ─── master tables ───
@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display  = ("name", "short_name", "thumb", "calories", "protein")
    search_fields = ("name",)
    readonly_fields = ("thumb",)

    def thumb(self, obj):
        return _thumb(obj.image, size=70)
    thumb.short_description = ""


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display  = ("name", "short_name", "thumb", "default_duration")
    search_fields = ("name",)
    readonly_fields = ("thumb",)

    def thumb(self, obj):
        return _thumb(obj.image, size=70)
    thumb.short_description = ""


@admin.register(AgeGroup)
class AgeGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "min_age", "max_age_display")
    ordering     = ("min_age",)

    def max_age_display(self, obj):
        return obj.max_age if obj.max_age is not None else "∞"
    max_age_display.short_description = "Max age"


# ─── dynamic inline for Module ───
@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "short_name",
        "type",
        "nutrition_category",
        "age_group",
        "icon_preview",
        "background_preview",
    )

    list_filter = ("type", "age_group")
    search_fields = ("name", "short_name", "tag_line")

    readonly_fields = ("icon_preview", "background_preview")

    fieldsets = (
        ("Basic Info", {
            "fields": (
                "name",
                "short_name",
                "type",
                "nutrition_category",
                "age_group",
            )
        }),
        ("UI Content", {
            "fields": (
                "tag_line",
                "action_btn",
            )
        }),
        ("Images", {
            "fields": (
                "icon_image",
                "icon_preview",
                "background_image",
                "background_preview",
            )
        }),
    )

    # ───────── image previews ─────────
    def icon_preview(self, obj):
        return _thumb(obj.icon_image, size=48)
    icon_preview.short_description = "Icon"

    def background_preview(self, obj):
        return _thumb(obj.background_image, size=90)
    background_preview.short_description = "Background"

    # ───────── dynamic inline handling ─────────
    def get_inline_instances(self, request, obj=None):

        # ADD view
        if obj is None:
            initial_type = request.GET.get("type")
            if initial_type == Module.NUTRITION:
                inline_cls = ModuleFoodInline
            elif initial_type == Module.LIFESTYLE:
                inline_cls = ModuleActivityInline
            else:
                return []
            return [inline_cls(self.model, self.admin_site)]

        # CHANGE view
        inline_cls = (
            ModuleFoodInline
            if obj.type == Module.NUTRITION
            else ModuleActivityInline
        )
        return [inline_cls(self.model, self.admin_site)]