# """
# Plan serializers with "completed" flag
# ──────────────────────────────────────
# • FoodSlim   – single ModuleFood row  (adds completed)
# • HabitSlim  – single ModuleActivity  (adds completed)
# • ModulePlanSerializer – top level
# """

# from django.apps import apps
# from django.utils import timezone
# from rest_framework import serializers

# Module      = apps.get_model("nutration", "Module")
# NutraEntry  = apps.get_model("nutration", "NutraEntry")   # ← daily log


# # ──────────────────── nutrition item ─────────────────────
# class FoodSlim(serializers.Serializer):
#     id      = serializers.IntegerField(source="food.id")
#     name    = serializers.CharField(source="food.name")
#     short_name    = serializers.CharField(source="food.short_name")
#     image   = serializers.SerializerMethodField()
#     serving = serializers.CharField(source="serving_size")
#     score   = serializers.IntegerField()

#     completed = serializers.SerializerMethodField()        # ← new

#     def get_image(self, obj):                              # ← NEW
#         img = obj.food.image
#         return img.url if img else None
    
#     def get_completed(self, obj):
#         request = self.context.get("request")
#         if not request or not request.user.is_authenticated:
#             return False

#         today = timezone.localdate()
#         return NutraEntry.objects.filter(
#             session__user=request.user,
#             session__date=today,
#             module=obj.module,
#             food=obj.food
#         ).exists()


# # ──────────────────── lifestyle habit ────────────────────
# class HabitSlim(serializers.Serializer):
#     id    = serializers.IntegerField(source="activity.id")
#     short_name  = serializers.CharField(source="activity.short_name")
#     name  = serializers.CharField(source="activity.name")
#     image   = serializers.SerializerMethodField() 
#     score = serializers.IntegerField()
#     rec   = serializers.CharField(source="recommendation", allow_blank=True)

#     completed = serializers.SerializerMethodField()        # ← new

#     def get_image(self, obj):                              # ← NEW
#         img = obj.activity.image
#         return img.url if img else None
    
#     def get_completed(self, obj):
#         request = self.context.get("request")
#         if not request or not request.user.is_authenticated:
#             return False

#         today = timezone.localdate()
#         return NutraEntry.objects.filter(
#             session__user=request.user,
#             session__date=today,
#             module=obj.module,
#             activity=obj.activity
#         ).exists()


# # ──────────────────── module block ───────────────────────
# class ModulePlanSerializer(serializers.ModelSerializer):
#     foods  = FoodSlim(source="module_foods", many=True, read_only=True,
#                       context={"request": None})   # placeholder
#     habits = HabitSlim(source="module_activities", many=True, read_only=True,
#                        context={"request": None})

#     class Meta:
#         model  = Module
#         fields = ("id", "name", "type", "foods", "habits")

#     # ensure nested serializers inherit the request object
#     def to_representation(self, instance):
#         self.fields["foods"].context.update(self.context)
#         self.fields["habits"].context.update(self.context)
#         return super().to_representation(instance)


"""
Plan serializers with "completed" flag
──────────────────────────────────────
• FoodSlim   – single ModuleFood row  (adds completed)
• HabitSlim  – single ModuleActivity  (adds completed + audio + video)
• ModulePlanSerializer – top level
"""

from django.apps import apps
from django.utils import timezone
from rest_framework import serializers

Module      = apps.get_model("nutration", "Module")
NutraEntry  = apps.get_model("nutration", "NutraEntry")   # ← daily log


# ──────────────────── nutrition item ─────────────────────
class FoodSlim(serializers.Serializer):
    id          = serializers.IntegerField(source="food.id")
    name        = serializers.CharField(source="food.name")
    short_name  = serializers.CharField(source="food.short_name")
    image       = serializers.SerializerMethodField()
    serving     = serializers.CharField(source="serving_size")
    score       = serializers.IntegerField()

    completed   = serializers.SerializerMethodField()      # ← NEW

    def get_image(self, obj):
        img = obj.food.image
        return img.url if img else None
    
    def get_completed(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        today = timezone.localdate()
        return NutraEntry.objects.filter(
            session__user=request.user,
            session__date=today,
            module=obj.module,
            food=obj.food
        ).exists()


# ──────────────────── lifestyle habit ────────────────────
class HabitSlim(serializers.Serializer):
    id          = serializers.IntegerField(source="activity.id")
    short_name  = serializers.CharField(source="activity.short_name")
    name        = serializers.CharField(source="activity.name")
    image       = serializers.SerializerMethodField()
    score       = serializers.IntegerField()
    rec         = serializers.CharField(source="recommendation", allow_blank=True)

    # ───── NEW MEDIA FIELDS ─────
    audio       = serializers.SerializerMethodField()
    video       = serializers.SerializerMethodField()

    completed   = serializers.SerializerMethodField()      # ← NEW

    def get_image(self, obj):
        img = obj.activity.image
        return img.url if img else None

    # NEW: return audio file URL
    def get_audio(self, obj):
        file = obj.audio
        return file.url if file else None

    # NEW: return video file URL
    def get_video(self, obj):
        file = obj.video
        return file.url if file else None
    
    def get_completed(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        today = timezone.localdate()
        return NutraEntry.objects.filter(
            session__user=request.user,
            session__date=today,
            module=obj.module,
            activity=obj.activity
        ).exists()


# ──────────────────── module block ───────────────────────
class ModulePlanSerializer(serializers.ModelSerializer):
    foods  = FoodSlim(source="module_foods", many=True, read_only=True)
    habits = HabitSlim(source="module_activities", many=True, read_only=True)

    background_image = serializers.SerializerMethodField()
    icon_image = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = (
            "id",
            "name",
            "short_name",
            "type",
            "action_btn",
            "background_image",
            "icon_image",
            "tag_line",
            "foods",
            "habits",
        )

    def get_background_image(self, obj):
        if not obj.background_image:
            return None
        file = obj.background_image
        return file.url if file else None

    def get_icon_image(self, obj):
        if not obj.icon_image:
            return None
        file = obj.icon_image
        return file.url if file else None

    # ensure nested serializers inherit request
    def to_representation(self, instance):
        self.fields["foods"].context.update(self.context)
        self.fields["habits"].context.update(self.context)
        return super().to_representation(instance)