from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model
from .models import OTP
from django.utils import timezone
import datetime

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'name',
            'display_name',
            'avatar_url',
            'timezone',
            'device_id',
            'role',
            'verified',
        )
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True},
        }

class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('email', 'name', 'password', 'device_id','fcm_token')
        extra_kwargs = {
            'password': {'write_only': True, 'required': True},
            'email': {'required': True},
            'name': {'required': False},  # Make name optional
            'device_id': {'required': False},  # Make device_id optional
            'fcm_token': {'required': False},  # Make device_id optional
        }

    def create(self, validated_data):
        # Create user with email as both email and username
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            name=validated_data.get('name'),
            device_id=validated_data.get('device_id'),
            fcm_token=validated_data.get('fcm_token'),
            username=validated_data['email'],  # Use email as username
        )
        return user

class SocialLoginSerializer(serializers.Serializer):
    social_id = serializers.CharField(required=True)
    social_auth_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    email = serializers.EmailField(required=True)
    name = serializers.CharField(required=False, allow_blank=True)
    photo_url = serializers.URLField(required=False, allow_blank=True)
    social_type = serializers.ChoiceField(choices=["google", "facebook", "apple"])
    device_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    fcm_token = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def create(self, validated_data):
        social_id   = validated_data['social_id']
        email       = validated_data['email']
        name        = validated_data.get('name', '')
        photo_url   = validated_data.get('photo_url', '')
        social_type = validated_data['social_type']
        fcm_token   = validated_data.get('fcm_token')
        device_id   = validated_data.get('device_id')  #  Use .get()

        user = User.objects.filter(social_id=social_id).first()

        if user:
            user.email = email
            user.name = name
            user.profile_image_url = photo_url
            user.social_type = social_type
            user.fcm_token = fcm_token or user.fcm_token
            user.device_id = device_id
            user.save()
            return user, False  # Existing user
        else:
            user = User.objects.create(
                social_id=social_id,
                email=email,
                username=email,
                name=name,
                profile_image_url=photo_url,
                social_type=social_type,
                fcm_token=fcm_token,
                device_id=device_id,
            )
            user.set_password(social_id)
            user.save()
            return user, True  # New us

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    device_id = serializers.CharField(required=False, allow_blank=True)
    fcm_token = serializers.CharField(required=False, allow_blank=True)
    print(email)
    print(password)
    print(device_id)
    print(fcm_token)
    def validate(self, attrs):
        request = self.context.get('request')
        user = authenticate(
            request=request,
            username=attrs['email'],
            password=attrs['password']
        )

        if not user:
            raise serializers.ValidationError(
                'Unable to log in with provided credentials.',
                code='authorization'
            )

        # Save device_id and fcm_token if provided
        device_id = attrs.get('device_id')
        fcm_token = attrs.get('fcm_token')
        updated = False

        if device_id and user.device_id != device_id:
            user.device_id = device_id
            updated = True

        if fcm_token and user.fcm_token != fcm_token:
            user.fcm_token = fcm_token
            updated = True

        if updated:
            user.save(update_fields=["device_id", "fcm_token"])
        print(user)

        attrs['user'] = user
        return attrs
class OTPSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    otp = serializers.CharField(max_length=4, min_length=4)  # Enforce 4 digits

    def validate(self, data):
        user_id = data.get('user_id')
        otp_code = data.get('otp')

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise serializers.ValidationError("User does not exist")

        try:
            otp = OTP.objects.get(user=user, code=otp_code)
            if not otp.is_valid():
                raise serializers.ValidationError("OTP has expired")
        except OTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP")

        data['user'] = user
        return data