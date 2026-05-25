from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model
from .models import OTP
from django.utils import timezone
from utils.country import DEFAULT_COUNTRY_CODE, normalize_country_code, resolve_country_code
from utils.user_profile_display import (
    apply_country_timezone_default,
    apply_display_name_to_user,
)
import datetime

User = get_user_model()


def _validate_country_code_field(value):
    if value in (None, ""):
        return None
    normalized = normalize_country_code(value)
    if not normalized:
        raise serializers.ValidationError(
            "country_code must be a 2-letter ISO code (e.g. CA, US)."
        )
    return normalized

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
            'country_code',
            'device_id',
            'role',
            'verified',
        )
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True},
        }

class RegisterSerializer(serializers.ModelSerializer):
    country_code = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2,
        default=DEFAULT_COUNTRY_CODE,
    )

    class Meta:
        model = User
        fields = ('email', 'name', 'password', 'device_id', 'fcm_token', 'country_code')
        extra_kwargs = {
            'password': {'write_only': True, 'required': True},
            'email': {'required': True},
            'name': {'required': False},  # Make name optional
            'device_id': {'required': False},  # Make device_id optional
            'fcm_token': {'required': False},  # Make device_id optional
        }

    def validate_country_code(self, value):
        if value in (None, ""):
            return DEFAULT_COUNTRY_CODE
        return _validate_country_code_field(value)

    def create(self, validated_data):
        country_code = validated_data.pop('country_code', DEFAULT_COUNTRY_CODE)
        # Create user with email as both email and username
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            name=validated_data.get('name'),
            device_id=validated_data.get('device_id'),
            fcm_token=validated_data.get('fcm_token'),
            country_code=country_code,
            username=validated_data['email'],  # Use email as username
        )
        apply_display_name_to_user(user, validated_data.get('name'))
        apply_country_timezone_default(user, country_code)
        user.save(update_fields=["display_name", "name", "timezone"])
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
    country_code = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2,
        default=DEFAULT_COUNTRY_CODE,
    )

    def validate_country_code(self, value):
        if value in (None, ""):
            return DEFAULT_COUNTRY_CODE
        return _validate_country_code_field(value)

    def create(self, validated_data):
        social_id   = validated_data['social_id']
        email       = validated_data['email']
        name        = validated_data.get('name', '')
        photo_url   = validated_data.get('photo_url', '')
        social_type = validated_data['social_type']
        fcm_token   = validated_data.get('fcm_token')
        device_id   = validated_data.get('device_id')  #  Use .get()
        country_code = validated_data.get('country_code', DEFAULT_COUNTRY_CODE)
        raw_cc = (getattr(self, "initial_data", None) or {}).get("country_code")

        user = User.objects.filter(social_id=social_id).first()

        if user:
            user.email = email
            apply_display_name_to_user(user, name)
            user.profile_image_url = photo_url
            user.social_type = social_type
            user.fcm_token = fcm_token or user.fcm_token
            user.device_id = device_id
            if raw_cc not in (None, ""):
                user.country_code = country_code
                apply_country_timezone_default(user, country_code)
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
                country_code=country_code,
            )
            apply_display_name_to_user(user, name)
            apply_country_timezone_default(user, country_code)
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