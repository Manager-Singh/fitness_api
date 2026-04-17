from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, OTP, Friendship, FriendInvite
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
from workouts.models import WorkoutSession, WorkoutEntry
from django.db.models import Sum, Count
from workouts.serializers_leaderboard import LeaderboardResponseSerializer
from nutration.models_log import NutraEntry

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
            # Send email
            # send_mail(
            #     subject,
            #     message,
            #     settings.DEFAULT_FROM_EMAIL,
            #     [user.email],
            #     fail_silently=False,
            # )
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
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

        request_type = request.data.get("type")  # forgot-otp or normal
        user = None

        # ✅ Case 1: Forgot Password → Use Email
        if request_type == "forgot-otp":
            email = request.data.get("email")

            if not email:
                return Response(
                    {"success": False, "message": "Email is required."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response(
                    {"success": False, "message": "User with this email not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

        # ✅ Case 2: Normal OTP → Use user_id
        else:
            user_id = request.data.get("user_id")

            if not user_id:
                return Response(
                    {"success": False, "message": "User ID is required."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                user = User.objects.get(id=int(user_id))
            except (User.DoesNotExist, ValueError, TypeError):
                return Response(
                    {"success": False, "message": "User not found."},
                    status=status.HTTP_404_NOT_FOUND
                )

        # ✅ Generate OTP
        otp_code = f"{secrets.randbelow(10000):04d}"
        expires_at = timezone.now() + datetime.timedelta(minutes=15)

        OTP.objects.update_or_create(
            user=user,
            defaults={
                "code": otp_code,
                "expires_at": expires_at,
            }
        )

        # ✅ Send Email
        subject = "Your One-Time Password (OTP)"
        message = f"""
            Hello,

            Your OTP is: {otp_code}

            This OTP is valid for 15 minutes.

            If you did not request this, please ignore.

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
                "success": True,
                "message": "OTP sent successfully.",
                "user_id": user.id
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
        subject = "Reset Password - OTP Verification"
        message = f"""Hello,

    We received a request to reset password your account.

    Your One-Time Password (OTP) is:

    {otp_code}

    This OTP is valid for 15 minutes. Please do not share it with anyone.

    If you did not request this OTP, you can safely ignore this email.

    Thanks,
    Team HeightMax
    """
        # send_mail(
        #     'Reset Password - OTP Verification',
        #     f'Your password reset OTP is: {otp_code}',
        #     settings.DEFAULT_FROM_EMAIL,
        #     [email],
        #     fail_silently=False,
        # )
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
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


class InviteFriendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        def _frontend_base_url():
            # Prefer explicit config; otherwise derive from request host.
            configured = getattr(settings, "FRONTEND_BASE_URL", None)
            if configured:
                return str(configured).rstrip("/")
            return f"{request.scheme}://{request.get_host()}".rstrip("/")

        existing = FriendInvite.objects.filter(
            inviter=request.user,
            accepted_by__isnull=True,
            expires_at__gte=timezone.now(),
        ).order_by("-created_at").first()
        if existing:
            base_url = _frontend_base_url()
            invite_link = f"{base_url}/invite?token={existing.invite_token}"
            return Response(
                {
                    "invite_token": existing.invite_token,
                    # Spec (Section 17.7): `invite_link`
                    "invite_link": invite_link,
                    # Backward-compat alias (keep for existing clients)
                    "invite_url": invite_link,
                    "expires_at": existing.expires_at,
                },
                status=status.HTTP_200_OK,
            )

        token = secrets.token_urlsafe(24)
        expires_at = timezone.now() + datetime.timedelta(days=7)
        invite = FriendInvite.objects.create(
            inviter=request.user,
            invite_token=token,
            expires_at=expires_at,
        )
        base_url = _frontend_base_url()
        invite_link = f"{base_url}/invite?token={invite.invite_token}"
        return Response(
            {
                "invite_token": invite.invite_token,
                # Spec (Section 17.7): `invite_link`
                "invite_link": invite_link,
                # Backward-compat alias (keep for existing clients)
                "invite_url": invite_link,
                "expires_at": invite.expires_at,
            },
            status=status.HTTP_200_OK,
        )


class AcceptFriendInviteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get("invite_token")
        if not token:
            return Response({"error": "invite_token is required"}, status=status.HTTP_400_BAD_REQUEST)

        invite = FriendInvite.objects.filter(invite_token=token).first()
        if not invite:
            return Response({"error": "invalid_invite_token"}, status=status.HTTP_404_NOT_FOUND)
        if invite.expires_at < timezone.now():
            return Response({"error": "invite_expired"}, status=status.HTTP_410_GONE)
        if invite.inviter_id == request.user.id:
            return Response({"error": "cannot_accept_own_invite"}, status=status.HTTP_400_BAD_REQUEST)

        existing = Friendship.objects.filter(
            Q(user_id_a=invite.inviter, user_id_b=request.user)
            | Q(user_id_a=request.user, user_id_b=invite.inviter)
        ).first()

        if existing:
            if existing.status != Friendship.STATUS_ACCEPTED:
                existing.status = Friendship.STATUS_ACCEPTED
                existing.save(update_fields=["status"])
            friendship = existing
        else:
            friendship = Friendship.objects.create(
                user_id_a=invite.inviter,
                user_id_b=request.user,
                status=Friendship.STATUS_ACCEPTED,
            )

        invite.accepted_by = request.user
        invite.save(update_fields=["accepted_by"])

        return Response(
            {
                "friendship_id": friendship.id,
                "status": friendship.status,
            },
            status=status.HTTP_200_OK,
        )


class FriendsLeaderboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page = max(int(request.query_params.get("page", 1)), 1)
        limit = min(max(int(request.query_params.get("limit", 50)), 1), 100)

        try:
            current_age = get_user_age(request.user)
        except Exception:
            current_age = 0
        current_is_adult = current_age >= 21

        accepted = Friendship.objects.filter(
            status=Friendship.STATUS_ACCEPTED,
        ).filter(
            user_id_a=request.user
        ) | Friendship.objects.filter(
            status=Friendship.STATUS_ACCEPTED,
            user_id_b=request.user
        )
        friend_ids = set()
        for rel in accepted:
            if rel.user_id_a_id == request.user.id:
                friend_ids.add(rel.user_id_b_id)
            else:
                friend_ids.add(rel.user_id_a_id)
        friend_ids.add(request.user.id)

        qs = User.objects.filter(id__in=friend_ids, is_active=True).annotate(
            score=Sum("workout_sessions__entries__points"),
            sessions_completed=Count("workout_sessions", distinct=True),
        )
        nutra_rows = (
            NutraEntry.objects.filter(session__user_id__in=friend_ids)
            .values("session__user_id")
            .annotate(total=Sum("score"))
        )
        nutrition_by_user = {int(r["session__user_id"]): int(r["total"] or 0) for r in nutra_rows}

        from utils.leaderboard import _current_validated_streak
        tier_entries = []
        today_local = timezone.localdate()
        for u in qs:
            try:
                user_age = get_user_age(u)
            except Exception:
                continue
            if (user_age >= 21) != current_is_adult:
                continue
            tier_entries.append(
                {
                    "user_id": u.id,
                    "display_name": (u.name or u.username or u.email or f"User {u.id}"),
                    "avatar_url": u.profile_image_url or None,
                    "points": int((u.score or 0) + nutrition_by_user.get(int(u.id), 0)),
                    "streak": _current_validated_streak(u, today_local),
                    "is_current_user": u.id == request.user.id,
                }
            )

        tier_entries.sort(key=lambda x: (-x["points"], -x["streak"], x["user_id"]))
        ranked = []
        prev_points = None
        rank = 0
        for idx, row in enumerate(tier_entries, start=1):
            if prev_points != row["points"]:
                rank = idx
                prev_points = row["points"]
            row["rank"] = rank
            ranked.append(row)

        current_user_entry = next((r for r in ranked if r["user_id"] == request.user.id), None)
        current_user_rank = current_user_entry["rank"] if current_user_entry else (len(ranked) + 1)

        total = len(ranked)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        entries = ranked[start_idx:end_idx]

        payload = {
            "view": "friends",
            "tier": "adult" if current_is_adult else "teen",
            "current_user_rank": current_user_rank,
            "entries": entries,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
            },
        }
        serializer = LeaderboardResponseSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RevokeFriendInviteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        invite_token = request.data.get("invite_token")
        friendship_id = request.data.get("friendship_id")

        if not invite_token and not friendship_id:
            return Response(
                {"error": "invite_token or friendship_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if invite_token:
            invite = FriendInvite.objects.filter(
                invite_token=invite_token,
                inviter=request.user,
            ).first()
            if not invite:
                return Response({"error": "invite_not_found"}, status=status.HTTP_404_NOT_FOUND)
            invite.delete()
            return Response({"message": "invite_revoked"}, status=status.HTTP_200_OK)

        friendship = Friendship.objects.filter(id=friendship_id).filter(
            Q(user_id_a=request.user) | Q(user_id_b=request.user)
        ).first()
        if not friendship:
            return Response({"error": "friendship_not_found"}, status=status.HTTP_404_NOT_FOUND)

        friendship.delete()
        return Response({"message": "friendship_removed"}, status=status.HTTP_200_OK)


class PendingFriendInvitesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        incoming = FriendInvite.objects.filter(
            expires_at__gte=timezone.now(),
        ).exclude(
            inviter=request.user,
        ).exclude(
            accepted_by__isnull=False,
        )

        outgoing = FriendInvite.objects.filter(
            inviter=request.user,
            expires_at__gte=timezone.now(),
            accepted_by__isnull=True,
        )

        incoming_payload = []
        for invite in incoming:
            incoming_payload.append(
                {
                    "invite_token": invite.invite_token,
                    "inviter_user_id": invite.inviter_id,
                    "inviter_name": invite.inviter.name or invite.inviter.username or invite.inviter.email,
                    "expires_at": invite.expires_at,
                }
            )

        outgoing_payload = []
        for invite in outgoing:
            outgoing_payload.append(
                {
                    "invite_token": invite.invite_token,
                    "expires_at": invite.expires_at,
                }
            )

        return Response(
            {
                "incoming": incoming_payload,
                "outgoing": outgoing_payload,
            },
            status=status.HTTP_200_OK,
        )