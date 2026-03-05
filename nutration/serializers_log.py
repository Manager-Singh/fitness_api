from rest_framework import serializers
from django.apps import apps

NutraSession = apps.get_model("nutration", "NutraSession")
NutraEntry   = apps.get_model("nutration", "NutraEntry")
Module       = apps.get_model("nutration", "Module")
Food         = apps.get_model("nutration", "Food")
Activity     = apps.get_model("nutration", "Activity")


class NutraEntryWriteSerializer(serializers.ModelSerializer):
    module_id = serializers.PrimaryKeyRelatedField(queryset=Module.objects.all(),
                                                   source="module")
    food_id = serializers.PrimaryKeyRelatedField(queryset=Food.objects.all(),
                                                 source="food",
                                                 required=False, allow_null=True)
    activity_id = serializers.PrimaryKeyRelatedField(queryset=Activity.objects.all(),
                                                     source="activity",
                                                     required=False, allow_null=True)

    class Meta:
        model  = NutraEntry
        fields = ("module_id", "food_id", "activity_id",
                  "servings", "score")

    def validate(self, attrs):
        has_food     = bool(attrs.get("food"))
        has_activity = bool(attrs.get("activity"))
        if has_food == has_activity:
            raise serializers.ValidationError("Send either food_id OR activity_id.")
        return attrs


class NutraEntryReadSerializer(serializers.ModelSerializer):
    item = serializers.SerializerMethodField()

    class Meta:
        model  = NutraEntry
        fields = ("id", "item", "servings", "score", "completed_at")

    def get_item(self, obj):
        if obj.food:
            return {"type": "food", "id": obj.food_id, "name": obj.food.name, "short_name": obj.food.short_name}
        return {"type": "habit", "id": obj.activity_id, "name": obj.activity.name,"short_name": obj.activity.short_name}


class NutraSessionSerializer(serializers.ModelSerializer):
    entries = NutraEntryReadSerializer(many=True, read_only=True)

    class Meta:
        model  = NutraSession
        fields = ("id", "date", "entries")
