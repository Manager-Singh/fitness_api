from rest_framework import serializers
from .models import UserPosturalOptimizationData, PosturalRecommendation

class PosturalRecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PosturalRecommendation
        fields = ['title', 'description']

class UserPosturalOptimizationDataSerializer(serializers.ModelSerializer):
    recommendations = PosturalRecommendationSerializer(many=True)

    class Meta:
        model = UserPosturalOptimizationData
        fields = [
            'summary', 'max_height_gain_inches', 'note',
            'spinal_compression', 'posture_collapse',
            'pelvic_tilt_back', 'leg_hamstring', 'recommendations'
        ]

    def create(self, validated_data):
        recommendations_data = validated_data.pop('recommendations')
        user = self.context['request'].user
        instance, _ = UserPosturalOptimizationData.objects.update_or_create(
            user=user,
            defaults=validated_data
        )
        instance.recommendations.all().delete()
        for rec in recommendations_data:
            PosturalRecommendation.objects.create(user_data=instance, **rec)
        return instance
