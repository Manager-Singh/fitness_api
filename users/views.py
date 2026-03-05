from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, OTP
from .serializers import (
    RegisterSerializer, 
    LoginSerializer,
    UserSerializer,
    OTPSerializer,
    SocialLoginSerializer
)
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
import secrets
import datetime
from utils.age import get_user_age
from user_profile.models import Payment,UserProfile
from django.db.models import Q
from utils.check_payment import check_subscription_or_response
from utils.free_subscription import activate_free_subscription

# class RegisterView(APIView):
#     permission_classes = [AllowAny]  # Allow registration without authentication
    
#     def post(self, request):
#         serializer = RegisterSerializer(data=request.data)
#         if serializer.is_valid():
#             user = serializer.save()
            
#             # Generate JWT tokens
#             refresh = RefreshToken.for_user(user)
#             access_token = str(refresh.access_token)
            
#             # Generate OTP
#             otp_code = f"{secrets.randbelow(10000):04d}"
#             expires_at = timezone.now() + datetime.timedelta(minutes=15)
            
#             OTP.objects.create(
#                 user=user,
#                 code=otp_code,
#                 expires_at=expires_at
#             )
            
#             # Send email with OTP
#             send_mail(
#                 'OTP Authentication',
#                 f'Your OTP is: {otp_code}',
#                 settings.DEFAULT_FROM_EMAIL,
#                 [user.email],
#                 fail_silently=False,
#             )
#             age = get_user_age(user,default='register')
#             return Response({
#                 'message': 'User registered successfully',
#                 'age':age,
#                 'user': UserSerializer(user).data,
#                 'access': access_token,
#                 'refresh': str(refresh),
#             }, status=status.HTTP_201_CREATED)
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            # 🔥 Auto activate free subscription on registration
            activate_free_subscription(user)

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            # Create OTP
            otp_code = f"{secrets.randbelow(10000):04d}"
            expires_at = timezone.now() + datetime.timedelta(minutes=15)

            OTP.objects.create(
                user=user,
                code=otp_code,
                expires_at=expires_at
            )

            # Send email
            send_mail(
                'OTP Authentication',
                f'Your OTP is: {otp_code}',
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )

            # 🧮 Age
            age = get_user_age(user, default='register')

            # 🟢 Check if paid or free plan exists
            has_paid = Payment.objects.filter(
                user=user,
                payment_status__iexact="succeeded"
            ).exists()

            # 🟢 Subscription details JSON (plan, days_left, expired, message...)
            subscription_response = check_subscription_or_response(user)
            subscription_data = subscription_response.data

            # 🟢 Profile info
            profile = UserProfile.objects.get(user=user)

            # 🔥 Final registration response (same as login response)
            return Response({
                'message': 'User registered successfully',
                'age': age,
                'has_paid': has_paid,
                'subscription': subscription_data,
                'last_scan': profile.last_scan,
                'user': UserSerializer(user).data,
                'access': access_token,
                'refresh': str(refresh),
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# class SocialRegisterView(APIView):
#     permission_classes = [AllowAny]
#     def post(self, request):
#         serializer = SocialLoginSerializer(data=request.data)
#         if serializer.is_valid():
#             user, created = serializer.save()
#             refresh = RefreshToken.for_user(user)
#             access_token = str(refresh.access_token)
#             age = get_user_age(user,default='register')
#             return Response({
#                 "message": "Login successful" if not created else "Registration successful",
#                 "status": "login" if not created else "register",
#                 'age':age,
#                 "user": UserSerializer(user).data,
#                 "access": access_token,
#                 "refresh": str(refresh),
#                 "otp_sent": False,
#             }, status=status.HTTP_200_OK)

#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class SocialRegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SocialLoginSerializer(data=request.data)
        if serializer.is_valid():
            user, created = serializer.save()

            # Generate tokens
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            # 👉 Age
            age = get_user_age(user, default='register')

            # 👉 If first time registration via social login → give free plan
            if created:
                activate_free_subscription(user)

            # 👉 Has paid/free active plan?
            has_paid = Payment.objects.filter(
                user=user,
                payment_status__iexact="succeeded"
            ).exists()

            # 👉 Subscription details JSON
            subscription_response = check_subscription_or_response(user)
            subscription_data = subscription_response.data

            # 👉 User profile
            profile = UserProfile.objects.get(user=user)

            # Final response matching login & register APIs
            return Response({
                "message": "Login successful" if not created else "Registration successful",
                "status": "login" if not created else "register",
                "age": age,
                "has_paid": has_paid,
                "subscription": subscription_data,
                "last_scan": profile.last_scan,
                "user": UserSerializer(user).data,
                "access": access_token,
                "refresh": str(refresh),
                "otp_sent": False,
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# class LoginView(APIView):
#     permission_classes = [AllowAny]  # Allow login without authentication
    
#     def post(self, request):
#         serializer = LoginSerializer(data=request.data)
#         if serializer.is_valid():
#             user = serializer.validated_data['user'] 
#             refresh = RefreshToken.for_user(user)
#             age = get_user_age(user,default='register')
#              #  Check if user has any successful payment
#             has_paid = Payment.objects.filter(
#                 user=user,
#                 Q(payment_status__iexact="succeeded") | Q(payment_status__iexact="free")
#             ).exists()
#             profile = UserProfile.objects.get(user=user)
            
#             return Response({
#                 'message': 'Login successful',
#                 'age':age,
#                 'has_paid': has_paid,
#                 'last_scan':profile.last_scan,
#                 'user': UserSerializer(user).data,
#                 'access': str(refresh.access_token),
#                 'refresh': str(refresh),
#             })
#         print(serializer.errors)
#         return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)

            # 👇 Age calculation
            age = get_user_age(user, default='register')

            # 👇 Check if user has paid or free plan
            has_paid = Payment.objects.filter(
                user=user,
                payment_status__iexact="succeeded"
            ).exists()

            # 👇 Get subscription info from utility
            subscription_response = check_subscription_or_response(user)
            subscription_data = subscription_response.data  # extract JSON data

            profile = UserProfile.objects.get(user=user)

            # 👇 Final login response
            return Response({
                'message': 'Login successful',
                'age': age,
                'has_paid': has_paid,
                'subscription': subscription_data,  # 🔥 integrated here
                'last_scan': profile.last_scan,
                'user': UserSerializer(user).data,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }, status=status.HTTP_200_OK)

        # Invalid credentials
        return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]  # Requires valid JWT token
    
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        # With JWT, you might want to add the token to a blacklist
        # Here we'll just return success as JWT is stateless
        return Response({'message': 'Logged out successfully'}, status=status.HTTP_200_OK)

class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            otp_code = serializer.validated_data['otp']

            otp = OTP.objects.filter(user=user, code=otp_code).order_by('-created_at').first()

            if otp and otp.is_valid():
                #  Delete OTP after successful verification
                otp.delete()
                #  Set user's verified timestamp
                user.verified = timezone.now()
                user.save()

                refresh = RefreshToken.for_user(user)
                return Response({
                    'success': True,
                    'message': 'OTP verified successfully',
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                })

            return Response({
                'success': False,
                'message': 'Invalid or expired OTP'
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
class ResendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        user_id = request.data.get('user_id')

        if not user_id:
            return Response(
                {'success': False, 'message': 'User ID is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(id=int(user_id))
        except (User.DoesNotExist, ValueError, TypeError):
            return Response(
                {'success': False, 'message': 'User not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Generate OTP
        otp_code = f"{secrets.randbelow(10000):04d}"
        expires_at = timezone.now() + datetime.timedelta(minutes=15)

        # Save OTP
        OTP.objects.update_or_create(
            user=user,
            defaults={
                'code': otp_code,
                'expires_at': expires_at,
            }
        )

        # Email content
        subject = "Your One-Time Password (OTP)"
        message = f"""Hello,

        We received a request to verify your account.

        Your One-Time Password (OTP) is:

        {otp_code}

        This OTP is valid for 15 minutes. Please do not share it with anyone.

        If you did not request this OTP, you can safely ignore this email.

        Thanks,
        Team HeightMax
        """

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return Response(
            {
                'success': True,
                'message': 'OTP resent successfully.',
                'user_id': user.id
            },
            status=status.HTTP_200_OK
        )
        
class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'success': False, 'message': 'Email is required.'}, status=400)
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'success': False, 'message': 'User not found.'}, status=404)

        otp_code = f"{secrets.randbelow(10000):04d}"
        expires_at = timezone.now() + datetime.timedelta(minutes=15)

        OTP.objects.update_or_create(
            user=user,
            defaults={
                'code': otp_code,
                'expires_at': expires_at,
                'created_at': timezone.now()
            }
        )

        send_mail(
            'Reset Password - OTP Verification',
            f'Your password reset OTP is: {otp_code}',
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )

        return Response({'success': True, 'message': 'OTP sent for password reset.', 'user_id': user.id})


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp_code = request.data.get('otp')
        new_password = request.data.get('new_password')

        if not all([email, otp_code, new_password]):
            return Response({'success': False, 'message': 'All fields are required.'}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'success': False, 'message': 'User not found.'}, status=404)

        otp = OTP.objects.filter(user=user, code=otp_code).order_by('-created_at').first()

        if otp and otp.is_valid():
            user.set_password(new_password)
            user.save()
            otp.delete()
            return Response({'success': True, 'message': 'Password reset successful.'})
        
        return Response({'success': False, 'message': 'Invalid or expired OTP.'}, status=400)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        current_password = request.data.get("current_password")
        new_password = request.data.get("new_password")

        if not all([current_password, new_password]):
            return Response({"success": False, "message": "All fields are required."}, status=400)

        if not user.check_password(current_password):
            return Response({"success": False, "message": "Current password is incorrect."}, status=400)

        user.set_password(new_password)
        user.save()

        return Response({"success": True, "message": "Password changed successfully."}, status=200)