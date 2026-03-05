from rest_framework import serializers
from .models import (
    AgeGroup, Module,
    Food, ModuleFood,
    Activity, ModuleActivity
)

# — Age —
class AgeGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AgeGroup
        fields = "__all__"

# — Nutrition —
class FoodSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Food
        fields = "__all__"

class ModuleFoodSerializer(serializers.ModelSerializer):
    food    = FoodSerializer(read_only=True)
    food_id = serializers.PrimaryKeyRelatedField(
        write_only=True, queryset=Food.objects.all(), source="food"
    )
    class Meta:
        model  = ModuleFood
        fields = ("id", "food", "food_id", "score", "serving_size", "details")

# — Lifestyle —
class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model  = Activity
        fields = "__all__"

class ModuleActivitySerializer(serializers.ModelSerializer):
    activity    = ActivitySerializer(read_only=True)
    activity_id = serializers.PrimaryKeyRelatedField(
        write_only=True, queryset=Activity.objects.all(), source="activity"
    )
    class Meta:
        model  = ModuleActivity
        fields = ("id", "activity", "activity_id",
                  "score", "recommendation", "details")

# — Module —
class ModuleSerializer(serializers.ModelSerializer):
    age_group   = AgeGroupSerializer(read_only=True)
    age_group_id = serializers.PrimaryKeyRelatedField(
        write_only=True, queryset=AgeGroup.objects.all(), source="age_group"
    )
    items  = ModuleFoodSerializer(source="module_foods", many=True, read_only=True)
    habits = ModuleActivitySerializer(source="module_activities",
                                      many=True, read_only=True)

    class Meta:
        model  = Module
        fields = "__all__"
