# workouts/serializers_leaderboard.py
from rest_framework import serializers

class LeaderboardEntrySerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    user_id = serializers.IntegerField()
    display_name = serializers.CharField()
    avatar_url = serializers.CharField(allow_blank=True, allow_null=True)
    points = serializers.IntegerField()
    streak = serializers.IntegerField()
    is_current_user = serializers.BooleanField()


class LeaderboardResponseSerializer(serializers.Serializer):
    view = serializers.CharField()
    tier = serializers.CharField()
    current_user_rank = serializers.IntegerField()
    entries = LeaderboardEntrySerializer(many=True)
    pagination = serializers.DictField()
    # Backward-compatible alias for clients expecting `rank` at top level.
    rank = serializers.IntegerField(source="current_user_rank", read_only=True)