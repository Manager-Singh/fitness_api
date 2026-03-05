# Exercise/serializers.py

from rest_framework import serializers
from .models import ExerciseItem, ExerciseSubmission

class ExerciseItemSerializer(serializers.ModelSerializer):
    
    image = serializers.SerializerMethodField()
    
    class Meta:
        model = ExerciseItem
        fields = '__all__'
    
    def get_image(self, obj):
        request = self.context.get('request')
        if obj.image:
            image_url = obj.image.url
            if not image_url.startswith('/uploads/'):
                image_url = '/uploads' + image_url  # <- ADD THIS
            if request is not None:
                return request.build_absolute_uri(image_url)
            return image_url
        return None

class ExerciseSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExerciseSubmission
        fields = '__all__'
