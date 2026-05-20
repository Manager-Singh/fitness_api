# workouts/serializers_leaderboard.py
from rest_framework import serializers

class LeaderboardEntrySerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    user_id = serializers.IntegerField()
    display_name = serializers.CharField()
    avatar_url = serializers.CharField(allow_blank=True, allow_null=True)
    country_code = serializers.CharField(allow_null=True, required=False)
    country_flag_emoji = serializers.CharField(allow_null=True, required=False)
    points = serializers.IntegerField()
    # Backward-compatible alias for older clients that render `score`.
    score = serializers.IntegerField(source="points", read_only=True)
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