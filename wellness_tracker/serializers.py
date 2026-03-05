# wellness/serializers.py

from rest_framework import serializers
from .models import WellnessItem, WellnessSubmission

class WellnessItemSerializer(serializers.ModelSerializer):
    
    image = serializers.SerializerMethodField()
    
    class Meta:
        model = WellnessItem
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

class WellnessSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WellnessSubmission
        fields = '__all__'
