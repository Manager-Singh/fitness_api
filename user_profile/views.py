from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import UserProfile, ProfileType, Payment
from posture.models import PostureImage
from payment_packages.models import PaymentPackage
from django.contrib.auth.models import User
import stripe 
from django.conf import settings
from django.forms.models import model_to_dict
import re
import json
from posture.serializers import PostureImageSerializer
from utils.chatgpt_service import generate_chatgpt_response
from utils.age import get_user_age
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from datetime import timedelta
import uuid
from utils.check_payment import check_subscription_or_response


stripe.api_key = settings.STRIPE_SECRET_KEY

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_profile_users_old(request):
    user = request.user
    
    # Validate data
    data = request.data
    profile_data = {
        'language': data.get('language'),
        'gender': data.get('gender'),
        'age': data.get('age'),
        'height_foot': data.get('height_foot'),
        'height_inch': data.get('height_inch'),
        'height_cm': data.get('height_cm'),
        'height_type': data.get('height_type'),
        'weight': data.get('weight'),
        'weight_unit': data.get('weight_unit'),
        'interests': data.get('interests'),
        'goal': data.get('goal'),
    }
    
    # Update or create user profile
    profile, created = UserProfile.objects.update_or_create(
        user=user,
        defaults=profile_data
    )
    
    # Update profile type if activity_level_type is provided
    if 'activity_level_type' in data:
        profile_type, created = ProfileType.objects.update_or_create(
            user=user,
            defaults={'activity_level_type': data['activity_level_type']}
        )
    
    # Update profile step if provided
    if 'profile_step' in data:
        user.profile_step = data['profile_step']
        user.save()
    
    # Safely convert to dict
    profile_data = model_to_dict(profile) if profile else None
    profile_type_data = model_to_dict(profile_type) if 'activity_level_type' in data else None

    # Return full user and profile data
    return Response({
        'message': 'Profile updated successfully',
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'profile_step': getattr(user, 'profile_step', None),
            'profile': profile_data,
            'profile_type': profile_type_data,
        }
    }, status=status.HTTP_200_OK)

# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def update_profile_users(request):

#     body = request.body  # raw bytes
#     body_data = json.loads(body.decode('utf-8'))  # convert to dict
#     print(body_data)
#     user = request.user
    
#     try:
#         profile = UserProfile.objects.get(user=user)
#     except UserProfile.DoesNotExist:
#         return Response({'error': 'User profile not found.'}, status=status.HTTP_404_NOT_FOUND)
    
#     # List of all possible fields that can be updated
#     update_fields = [
#         'language', 'gender', 'age', 'ethnicity',
#         'current_height_foot', 'current_height_inch', 'current_height_cm', 'current_height_type',
#         'ideal_height_foot', 'ideal_height_inch', 'ideal_height_cm', 'ideal_height_type',
#         'father_height_foot', 'father_height_inch', 'father_height_cm', 'father_height_type',
#         'mother_height_foot', 'mother_height_inch', 'mother_height_cm', 'mother_height_type',
#         'activity_level_question', 'activity_level_answer', 'activity_level_all_option',
#         'sitting_hours_question',
#         'sitting_hours_options',
#         'sitting_hours_answer',
#         'posture_and_flexibility_question_one', 'posture_and_flexibility_answer_one',
#         'posture_and_flexibility_question_one_all_option',
#         'posture_and_flexibility_question_two', 'posture_and_flexibility_answer_two',
#         'posture_and_flexibility_question_two_all_option',
#         'posture_and_flexibility_question_three', 'posture_and_flexibility_answer_three',
#         'posture_and_flexibility_question_three_all_option',
#         'sleep_quality_and_position_question_one', 'sleep_quality_and_position_answer_one',
#         'sleep_quality_and_position_question_two', 'sleep_quality_and_position_answer_two',
#         'sleep_quality_and_position_question_two_all_option',
#         'sleep_hours_question',
#         'sleep_hours_options',
#         'sleep_hours_answer',
#         'touch_toes_wt_bending_knees_question',
#         'touch_toes_wt_bending_knees_options',
#         'touch_toes_wt_bending_knees_answer',
#         'discomfort_in_body_during_movement_question',
#         'discomfort_in_body_during_movement_options',
#         'discomfort_in_body_during_movement_answer',
#         'main_goal_with_heightmax_question',
#         'main_goal_with_heightmax_options',
#         'main_goal_with_heightmax_answer',
#         # 'sitting_hours_question',
#         # 'sitting_hours_options',
#         # 'sitting_hours_answer',
#         'g_p_height_change',
#         'g_p_shoe_pant_growth',
#         'g_p_voice_stage',
#         'g_p_facial_armpit_hair',
#         'g_p_looks',
        
#     ]

    
#     # Create update dictionary with only the fields that exist in the request
#     update_data = {}
#     for field in update_fields:
#         if field in request.data:
#             update_data[field] = request.data[field]
    
#     # Update the profile
#     for key, value in update_data.items():
#         setattr(profile, key, value)
#     profile.save()
    
#     # Update profile step if provided
#     if 'profile_step' in request.data:
#         user.profile_step = request.data['profile_step']
#         user.save()
    
#     profile_data = model_to_dict(profile)

#     return Response({
#         'message': 'Profile updated successfully',
#         'user': {
#             'id': user.id,
#             'username': user.username,
#             'email': user.email,
#             'profile_step': getattr(user, 'profile_step', None),
#             'profile': profile_data
#         }
#     }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_profile_users(request):

    user = request.user

    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        return Response({'error': 'User profile not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Get all model fields dynamically
    model_fields = [field.name for field in profile._meta.fields]

    # Remove protected fields (important ⚠️)
    protected_fields = ['id', 'user']
    allowed_fields = [f for f in model_fields if f not in protected_fields]

    # Update dynamically
    for key, value in request.data.items():
        if key in allowed_fields:
            setattr(profile, key, value)

    profile.save()

    # Update profile_step separately (belongs to User model)
    if 'profile_step' in request.data:
        user.profile_step = request.data['profile_step']
        user.save()

    profile_data = model_to_dict(profile)

    return Response({
        'message': 'Profile updated successfully',
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'profile_step': getattr(user, 'profile_step', None),
            'profile': profile_data
        }
    }, status=status.HTTP_200_OK)

# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def create_payment_intent(request):
#     try:
#         print(request.data)
#         raw_amount = request.data.get('amount')
#         package_id = request.data.get('package_id')

#         # Use Decimal for accuracy
#         amount = Decimal(raw_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

#         if amount < Decimal('0.50'):
#             return Response({'error': 'Minimum amount must be $0.50'}, status=400)

#         # Convert to cents
#         c_amount = int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))
#         # Create the PaymentIntent
#         intent = stripe.PaymentIntent.create(
#             amount=c_amount,
#             currency='usd',
#         )
        
#         # Save to database
#         payment = Payment.objects.create(
#             user=request.user,
#             payment_id=intent.id,
#             package_id=package_id,
#             amount=amount,  # Convert from cents to dollars
#             currency='usd'
#         )
        
#         return Response({
#             'clientSecret': intent.client_secret,
#             'paymentIntentdata': {
#                 'id': intent.id,
#                 'amount': amount,
#                 'currency': intent.currency,
#                 'status': intent.status
#             }
#         })
#     except Exception as e:
#         return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_payment_intent(request):
    try:
        # ❌ REMOVE print(request.data) — never log raw request data

        raw_amount = request.data.get('amount')
        package_id = request.data.get('package_id')

        # ✅ Validate required fields
        if raw_amount is None or package_id is None:
            return Response(
                {'error': 'amount and package_id are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ Validate & normalize amount safely
        try:
            amount = Decimal(str(raw_amount)).quantize(
                Decimal('0.01'),
                rounding=ROUND_HALF_UP
            )
        except Exception:
            return Response(
                {'error': 'Invalid amount format.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if amount < Decimal('0.50'):
            return Response(
                {'error': 'Minimum amount must be $0.50'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ Validate package existence (prevents fake package_id)
        try:
            package = PaymentPackage.objects.get(id=package_id)
        except PaymentPackage.DoesNotExist:
            return Response(
                {'error': 'Invalid package_id.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # ✅ Convert dollars → cents (Stripe requirement)
        cents_amount = int(
            (amount * 100).to_integral_value(rounding=ROUND_HALF_UP)
        )

        # ✅ Create Stripe PaymentIntent (BACKEND AUTHORITATIVE)
        intent = stripe.PaymentIntent.create(
            amount=cents_amount,
            currency='usd',
            metadata={
                "user_id": request.user.id,
                "package_id": package.id,
                "package_name": package.name
            }
        )

        # ✅ Persist intent immediately (audit-safe)
        Payment.objects.create(
            user=request.user,
            package=package,
            payment_id=intent.id,
            amount=amount,
            currency='usd',
            payment_status=intent.status
        )

        # ✅ Return only what frontend needs
        return Response({
            'clientSecret': intent.client_secret,
            'payment_intent': {
                'id': intent.id,
                'amount': str(amount),
                'currency': intent.currency,
                'status': intent.status
            }
        }, status=status.HTTP_200_OK)

    except stripe.error.StripeError as e:
        return Response(
            {'error': 'Stripe error', 'details': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

    except Exception as e:
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# def parse_complete_response(raw_response):
#     """
#     Convert a Stripe PaymentIntent string into a valid JSON string
#     """
#     # Step 1: Remove outer quotes if present
#     if isinstance(raw_response, str) and raw_response.startswith('"'):
#         raw_response = raw_response.strip('"')

#     # Step 2: Remove 'PaymentIntent(' prefix and trailing ')'
#     if raw_response.startswith("PaymentIntent(") and raw_response.endswith(")"):
#         raw_response = raw_response[len("PaymentIntent("):-1]

#     # Step 3: Use a better pattern to split key-value pairs
#     # Handle values that may contain colons or commas by splitting only on first colon
#     kv_pairs = re.split(r', (?=\w+:)', raw_response)  # split on comma followed by a key

#     response_dict = {}
#     for pair in kv_pairs:
#         if ':' not in pair:
#             continue  # skip invalid
#         key, value = pair.split(':', 1)  # split only on first colon
#         key = key.strip()
#         value = value.strip()

#         # Convert to correct type
#         if value.isdigit():
#             value = int(value)
#         elif value.lower() == "false":
#             value = False
#         elif value.lower() == "true":
#             value = True
#         elif value.lower() == "null":
#             value = None
#         else:
#             value = value.strip()

#         response_dict[key] = value

#     return response_dict

def parse_complete_response(raw_response):
    """
    Safely convert Stripe response to JSON.
    Accepts dict, StripeObject, or JSON string.
    """

    # Case 1: Already a dict (best case)
    if isinstance(raw_response, dict):
        return raw_response

    # Case 2: Stripe object
    try:
        if hasattr(raw_response, "to_dict"):
            return raw_response.to_dict()
    except Exception:
        pass

    # Case 3: JSON string
    if isinstance(raw_response, str):
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError:
            return {"raw_response": raw_response}

    # Fallback (never crash payment flow)
    return {"raw_response": str(raw_response)}


# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def save_payment_intent(request):
#     try:
#         payment_id = request.data.get('payment_id')
#         payment = Payment.objects.get(payment_id=payment_id, user=request.user)

#         payment.payment_status = request.data.get('payment_status')
#         payment.payment_method = request.data.get('payment_method')

#         raw_response = request.data.get('complete_response')
#         parsed_response = parse_complete_response(raw_response)
#         payment.complete_response = json.dumps(parsed_response)

#         payment.save()

#         # Optional profile_step update
#         profile_step = request.data.get('profile_step')
#         if profile_step is not None:
#             request.user.profile_step = profile_step
#             request.user.save()
            
#          #  Get age
#         try:
#             age = get_user_age(request.user)
#         except Exception:
#             age = None

#         return Response({'message': 'Payment saved successfully','age':age})

#     except Payment.DoesNotExist:
#         return Response({'error': 'Payment not found'}, status=status.HTTP_404_NOT_FOUND)
#     except Exception as e:
#         return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_payment_intent(request):
    try:
        payment_id = request.data.get('payment_id')
        if not payment_id:
            return Response(
                {'error': 'payment_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        payment = Payment.objects.get(
            payment_id=payment_id,
            user=request.user
        )

        # 🔒 AUTHORITATIVE STRIPE VERIFICATION
        intent = stripe.PaymentIntent.retrieve(payment.payment_id)

        # ✅ Update ONLY from Stripe (never frontend)
        payment.payment_status = intent.status
        payment.payment_method = (
            intent.payment_method_types[0]
            if intent.payment_method_types
            else None
        )
        payment.complete_response = json.dumps(intent)
        payment.save()

        # ✅ Paid plan overrides free plan
        if intent.status == "succeeded":
            Payment.objects.filter(
                user=request.user,
                payment_status='free'
            ).update(payment_status='expired')

        # Optional profile step update
        profile_step = request.data.get('profile_step')
        if profile_step is not None:
            request.user.profile_step = profile_step
            request.user.save()

        # Optional derived age (non-blocking)
        try:
            age = get_user_age(request.user)
        except Exception:
            age = None

        return Response({
            'message': 'Payment verified and saved successfully',
            'payment_status': intent.status,
            'age': age
        }, status=status.HTTP_200_OK)

    except Payment.DoesNotExist:
        return Response(
            {'error': 'Payment not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    except stripe.error.StripeError as e:
        return Response(
            {'error': 'Stripe verification failed', 'details': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

    except Exception:
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_report(request):
    try:
        postures = PostureImage.objects.filter(user=request.user)
        if not postures.exists():
            return Response({'error': 'Posture Details not found'}, status=status.HTTP_404_NOT_FOUND)

        # Get the latest front and side postures (single objects)
        latest_front = postures.filter(pose_type="front").order_by('-created_at').first()
        latest_side = postures.filter(pose_type="side").order_by('-created_at').first()

        # Serialize them (no `many=True` since they're single objects)
        front_serialized = PostureImageSerializer(latest_front).data if latest_front else None
        side_serialized = PostureImageSerializer(latest_side).data if latest_side else None

        return Response({
            'message': 'Posture Details fetched successfully',
            'front': front_serialized,  # Single object (not a list)
            'side': side_serialized,    # Single object (not a list)
        })

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_profile(request):
    user = request.user

    try:
        profile = UserProfile.objects.get(user=user)
        profile_data = model_to_dict(profile)
    except UserProfile.DoesNotExist:
        profile_data = None

    try:
        profile_type = ProfileType.objects.get(user=user)
        profile_type_data = model_to_dict(profile_type)
    except ProfileType.DoesNotExist:
        profile_type_data = None

    # Get current active package
    current_package = None
    try:
        latest_payment = user.payments.filter(payment_status='succeeded').latest('created_at')
        package = latest_payment.package

        # Check active status (within duration)
        created_at = latest_payment.created_at
        duration = getattr(package, 'duration', )  # default 30 if not defined
        duration_days = int(duration)*30
        expires_at = created_at + timedelta(days=duration_days)
        


        if timezone.now() <= expires_at:
            is_active = True
        else:
            is_active = False
            
        current_package = {
            'package_id': package.id,
            'title': package.name,
            'description': package.description,
            'amount': str(latest_payment.amount),
            'currency': latest_payment.currency,
            'payment_date': created_at,
            'expires_at': expires_at,
            'is_active': is_active,
            'duration_days': duration_days
        }

    except Payment.DoesNotExist:
        current_package = None
    subscription_status = check_subscription_or_response(user)
    if subscription_status.data.get("expired", True):
        return subscription_status  # contains message + 403 status
        
    subscription_data = subscription_status.data
    
    return Response({
        'message': 'Profile retrieved successfully',
        'data': {
            'id': user.id,
            'name': user.name,
            'username': user.username,
            'email': user.email,
            'social_type': user.social_type,
            'profile_image_url': user.profile_image_url,
            'profile_step': getattr(user, 'profile_step', None),
            'profile': profile_data,
            'profile_type': profile_type_data,
            'current_package': current_package,
            'subscription': subscription_data,
        }
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def subscribe_free_plan(request):
    """
    ✅ Activate a free plan for the authenticated user.
    - Checks if user already has an active subscription (paid or free)
    - If expired, allows new free plan activation
    - If active, blocks duplicate activation
    - Creates a Payment entry with payment_status='free'
    """
    try:
        user = request.user
        package_id = request.data.get('package_id')

        if not package_id:
            return Response({'error': 'package_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Fetch package safely
        try:
            package = PaymentPackage.objects.get(id=package_id)
        except PaymentPackage.DoesNotExist:
            return Response({'error': 'Invalid package ID.'}, status=status.HTTP_404_NOT_FOUND)

        # ✅ Ensure this is a free package
        if not package.is_free:
            return Response({'error': 'This package is not a free plan.'}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Check if user already has any active subscription (free or paid)
        subscription_status = check_subscription_or_response(user)
        if not subscription_status.data.get("expired", True):
            return Response({
                "error": "You already have an active subscription.",
                "active_plan": subscription_status.data.get("plan"),
                "active_plan_status": True,
                "days_left": subscription_status.data.get("days_left"),
                "message": subscription_status.data.get("message")
            }, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Create a "virtual" payment record for the new free plan
        payment = Payment.objects.create(
            user=user,
            package=package,
            payment_id=f"FREE-{uuid.uuid4().hex[:8]}",
            payment_status='free',
            payment_method='none',
            amount=Decimal('0.00'),
            currency='usd',
            complete_response='Free plan activation'
        )

        return Response({
            'message': 'Free plan activated successfully.',
            'payment_id': payment.payment_id,
            'package_name': package.name,
            'duration': package.get_duration_display(),
            'amount': str(payment.amount),
            'status': payment.payment_status
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)