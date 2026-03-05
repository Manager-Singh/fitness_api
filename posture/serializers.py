from rest_framework import serializers
from .models import PostureImage
from django.core.files.uploadedfile import UploadedFile
from tempfile import NamedTemporaryFile
import os
from .utils import analyze_posture


class PostureImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    verification_status = serializers.SerializerMethodField()
    height_loss_inches = serializers.SerializerMethodField()
    posture_defects = serializers.SerializerMethodField()

    class Meta:
        model = PostureImage
        fields = (
            'id', 'user', 'image', 'image_url', 'uploaded_type', 'detected_type',
            'verification_status', 'created_at', 'posture_score', 'pose_type',
            'details', 'recommendations', 'height_loss_inches', 'posture_defects',
        )
        read_only_fields = (
            'id', 'user', 'image_url', 'detected_type', 'verification_status',
            'created_at', 'posture_score', 'pose_type', 'details',
            'recommendations', 'height_loss_inches', 'posture_defects',
        )
        extra_kwargs = {
            'image': {'write_only': True}
        }

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and hasattr(obj.image, 'url'):
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None

    def get_verification_status(self, obj):
        if not obj.uploaded_type or not obj.detected_type:
            return "unverified"
        return "verified" if obj.uploaded_type == obj.detected_type else "mismatch"

    def get_height_loss_inches(self, obj):
        if obj.details and isinstance(obj.details, dict):
            return obj.details.get('height_loss_inches', {})
        return {}

    def get_posture_defects(self, obj):
        if obj.details and isinstance(obj.details, dict):
            return obj.details.get('posture_defects', [])
        return []

    def validate_uploaded_type(self, value):
        value = value.lower()
        if value not in ['front', 'side']:
            raise serializers.ValidationError('Upload type must be either "front" or "side".')
        return value

    def validate_image(self, value):
        if not value or not isinstance(value, UploadedFile):
            raise serializers.ValidationError('Invalid or missing image file.')

        valid_extensions = ['.jpg', '.jpeg', '.png', '.webp']
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in valid_extensions:
            raise serializers.ValidationError(f'Unsupported format. Allowed: {", ".join(valid_extensions)}')

        max_size = 5 * 1024 * 1024  # 5MB
        if value.size > max_size:
            raise serializers.ValidationError('Image too large (max 5MB).')

        return value

    def validate(self, attrs):
        request = self.context.get('request')
        uploaded_file = attrs.get('image')
        uploaded_type = attrs.get("uploaded_type")

        if not request:
            raise serializers.ValidationError({'error': 'Request context is missing'})
        if not uploaded_file:
            raise serializers.ValidationError({'error': 'Image not found in request'})

        ext = os.path.splitext(uploaded_file.name)[1].lower()
        with NamedTemporaryFile(delete=True, suffix=ext) as temp_file:
            for chunk in uploaded_file.chunks():
                temp_file.write(chunk)
            temp_file.flush()

            try:
                result = analyze_posture(temp_file.name, expected_pose_type=uploaded_type)

                if "error" in result:
                    raise serializers.ValidationError(result)

                detected_type = result.get("pose_type", None)
                if not detected_type:
                    raise serializers.ValidationError({"error": "Pose type could not be determined"})

                attrs['detected_type'] = detected_type
                attrs['_analysis_result'] = result

            except serializers.ValidationError:
                raise
            except Exception as e:
                raise serializers.ValidationError({
                    'error': 'Posture analysis failed during validation',
                    'details': str(e)
                })

        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request and request.user.is_authenticated else None

        if not user:
            raise serializers.ValidationError({'error': 'Authentication required'})

        uploaded_type = validated_data.get('uploaded_type')
        uploaded_file = validated_data.get('image')
        result = validated_data.pop('_analysis_result', {})

        posture_image = PostureImage.objects.create(
            user=user,
            uploaded_type=uploaded_type,
            image=uploaded_file,
            detected_type=result.get("pose_type"),
            pose_type=result.get("pose_type"),
            posture_score=result.get("posture_score"),
            details=result.get("details"),
            recommendations=result.get("recommendations"),
        )

        return posture_image

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['is_verified'] = instance.uploaded_type == instance.detected_type
        data['status'] = 'verified' if data['is_verified'] else 'unverified'
        return data
