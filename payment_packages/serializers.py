# # serializers.py
# from rest_framework import serializers
# from .models import PaymentPackage
# from user_profile.models import Payment
# from datetime import timedelta
# from django.utils import timezone

# class PaymentSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Payment
#         fields = ['payment_id', 'payment_status', 'payment_method', 'amount', 'currency', 'created_at']

# class PaymentPackageSerializer(serializers.ModelSerializer):
#     user_payment = serializers.SerializerMethodField()
#     is_active = serializers.SerializerMethodField()
#     days_left = serializers.SerializerMethodField()
#     duration_display = serializers.SerializerMethodField()

#     class Meta:
#         model = PaymentPackage
#         # fields = '__all__'  # or list specific fields + 'user_payment', 'is_active'
#         fields = '__all__'  # includes model fields

#     def get_duration_display(self, obj):
#         return obj.get_duration_display()
    
#     def get_user_payment(self, obj):
#         user = self.context.get('request').user
#         try:
#             payment = Payment.objects.filter(
#                 user=user,
#                 package=obj,
#                 payment_status='succeeded'
#             ).latest('created_at')
#             return PaymentSerializer(payment).data
#         except Payment.DoesNotExist:
#             return None

#     def get_is_active(self, obj):
#         user = self.context.get('request').user
#         try:
#             payment = Payment.objects.filter(
#                 user=user,
#                 package=obj,
#                 payment_status='succeeded'
#             ).latest('created_at')

#             expiry_date = payment.created_at + timedelta(days=30 * int(obj.duration))
#             return timezone.now() < expiry_date
#         except Payment.DoesNotExist:
#             return False
        
#     def get_days_left(self, obj):
#         user = self.context.get('request').user
#         try:
#             payment = Payment.objects.filter(
#                 user=user,
#                 package=obj,
#                 payment_status='succeeded'
#             ).latest('created_at')
#             expiry_date = payment.created_at + timedelta(days=30 * int(obj.duration))
#             days_remaining = (expiry_date - timezone.now()).days
#             return max(days_remaining, 0)
#         except (Payment.DoesNotExist, ValueError, TypeError):
#             return 0 


from rest_framework import serializers
from .models import PaymentPackage
from user_profile.models import Payment
from datetime import timedelta
from django.utils import timezone


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['payment_id', 'payment_status', 'payment_method', 'amount', 'currency', 'created_at']


class PaymentPackageSerializer(serializers.ModelSerializer):
    user_payment = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    days_left = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()

    class Meta:
        model = PaymentPackage
        fields = '__all__'

    def get_duration_display(self, obj):
        return obj.get_duration_display()

    def _get_user(self):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        return request.user

    def _has_active_free_plan(self, user):
        free_payment = Payment.objects.filter(
            user=user,
            package__is_free=True,
            payment_status='succeeded'
        ).order_by('-created_at').first()

        if not free_payment:
            return False

        expiry_date = free_payment.created_at + timedelta(days=30 * int(free_payment.package.duration))
        return timezone.now() < expiry_date

    def get_user_payment(self, obj):
        user = self._get_user()
        if not user:
            return None

        payment = Payment.objects.filter(
            user=user,
            package=obj,
            payment_status='succeeded'
        ).order_by('-created_at').first()

        return PaymentSerializer(payment).data if payment else None

    def get_is_active(self, obj):
        user = self._get_user()
        if not user:
            return False

        latest_payment = Payment.objects.filter(
            user=user,
            payment_status='succeeded'
        ).order_by('-created_at').first()

        if not latest_payment:
            return False

        expiry_date = latest_payment.created_at + timedelta(days=30 * int(latest_payment.package.duration))

        if timezone.now() > expiry_date:
            return False

        return latest_payment.package_id == obj.id

    def get_days_left(self, obj):
        user = self._get_user()
        if not user:
            return 0

        latest_payment = Payment.objects.filter(
            user=user,
            payment_status='succeeded'
        ).order_by('-created_at').first()

        if not latest_payment:
            return 0

        if latest_payment.package_id != obj.id:
            return 0

        expiry_date = latest_payment.created_at + timedelta(days=30 * int(latest_payment.package.duration))

        return max((expiry_date - timezone.now()).days, 0)