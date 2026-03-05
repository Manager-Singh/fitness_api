# workouts/serializers_leaderboard.py
from rest_framework import serializers

class LeaderboardEntrySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    username = serializers.CharField()
    profile_image_url = serializers.CharField()
    score = serializers.IntegerField()
    sessions_completed = serializers.IntegerField()
    rank = serializers.IntegerField()