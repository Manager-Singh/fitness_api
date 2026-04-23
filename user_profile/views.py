from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
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
import logging
from posture.serializers import PostureImageSerializer
from utils.chatgpt_service import generate_chatgpt_response
from utils.age import get_user_age
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from datetime import timedelta, date, datetime

logger = logging.getLogger(__name__)
import uuid
from utils.check_payment import check_subscription_or_response
from utils.streaks import get_user_streaks
from users.models import DailyLog, HeightLedger
from users.spec_runtime import get_user_runtime_state_snapshot
from workouts.models import UserRoutine
from django.db.models import Sum
from utils.posture.height_constants import (
    ADULT_AGE_MAX,
    ADULT_MIN_AGE,
    MPH_SIMPLE_CM_MAX,
    MPH_SIMPLE_CM_MIN,
    MSG_ADULT_AGE_RANGE,
    MSG_BASE_HEIGHT_LOCKED,
    MSG_FATHER_HEIGHT_RANGE,
    MSG_MOTHER_HEIGHT_RANGE,
    MSG_MPH_OUT_OF_RANGE,
    MSG_TEEN_DOB_AGE_RANGE,
    MSG_TEEN_REQUIRES_DOB,
    MSG_TEEN_REQUIRES_PARENTS,
    MSG_TEEN_UI_AGE_RANGE,
    MSG_USER_HEIGHT_RANGE,
    MSG_WINGSPAN_RANGE,
    PARENT_HEIGHT_CM_MAX,
    PARENT_HEIGHT_CM_MIN,
    TEEN_MAX_AGE,
    TEEN_MIN_AGE,
    USER_HEIGHT_CM_MAX,
    USER_HEIGHT_CM_MIN,
    WINGSPAN_CM_MAX,
    WINGSPAN_CM_MIN,
    compute_mph_simple_cm,
    normalize_sex,
)


stripe.api_key = settings.STRIPE_SECRET_KEY

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_profile_users_old(request):
    """Legacy alias kept for backwards compatibility.

    Routes to the canonical onboarding validator so Section-2 rules remain
    consistent for all clients.
    """
    return update_profile_users(request)

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
    # Debug visibility for client integration (prints only in DEBUG mode).
    if getattr(settings, "DEBUG", False):
        try:
            print("update-profile request body:", dict(request.data))
        except Exception:
            print("update-profile request body (unprintable)")

    def _is_truthy(value):
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "y", "confirm", "confirmed"}

    def _as_float(value, field_name):
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be numeric.")

    def _bound(value, lo, hi, message):
        if value is None:
            return
        if value < lo or value > hi:
            raise ValueError(message)

    user = request.user

    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        return Response({'error': 'User profile not found.'}, status=status.HTTP_404_NOT_FOUND)

    birth_date_parsed = None
    confirm_outlier = _is_truthy(request.data.get("confirm_outlier"))
    raw_bd = request.data.get("birth_date")
    if raw_bd not in (None, ""):
        try:
            birth_date_parsed = datetime.strptime(str(raw_bd).strip()[:10], "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "birth_date must be YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def _age_exact_years(dob: date) -> float:
        return (date.today() - dob).days / 365.2425

    age_num = None
    mph_cm = None
    try:
        current_height_cm = _as_float(
            request.data.get("current_height_cm", profile.current_height_cm), "current_height_cm"
        )
        father_height_cm = _as_float(
            request.data.get("father_height_cm", profile.father_height_cm), "father_height_cm"
        )
        mother_height_cm = _as_float(
            request.data.get("mother_height_cm", profile.mother_height_cm), "mother_height_cm"
        )
        wingspan_cm = _as_float(request.data.get("wingspan_cm"), "wingspan_cm")
        age_val = request.data.get("age", profile.age)
        age_num = None
        if age_val not in (None, ""):
            age_num = _as_float(age_val, "age")

        tier = (getattr(user, "account_tier", None) or "").strip().lower()
        if tier == "teen":
            is_teen = True
        elif tier == "adult":
            is_teen = False
        else:
            if age_num is not None:
                is_teen = TEEN_MIN_AGE <= age_num <= TEEN_MAX_AGE
            elif profile.birth_date or birth_date_parsed:
                dob0 = birth_date_parsed or profile.birth_date
                ae0 = _age_exact_years(dob0)
                is_teen = TEEN_MIN_AGE <= ae0 < ADULT_MIN_AGE
            else:
                is_teen = False

        _bound(current_height_cm, USER_HEIGHT_CM_MIN, USER_HEIGHT_CM_MAX, MSG_USER_HEIGHT_RANGE)
        _bound(father_height_cm, PARENT_HEIGHT_CM_MIN, PARENT_HEIGHT_CM_MAX, MSG_FATHER_HEIGHT_RANGE)
        _bound(mother_height_cm, PARENT_HEIGHT_CM_MIN, PARENT_HEIGHT_CM_MAX, MSG_MOTHER_HEIGHT_RANGE)
        if "wingspan_cm" in request.data and request.data.get("wingspan_cm") not in (None, ""):
            _bound(wingspan_cm, WINGSPAN_CM_MIN, WINGSPAN_CM_MAX, MSG_WINGSPAN_RANGE)

        if not is_teen and age_num is not None:
            _bound(age_num, float(ADULT_MIN_AGE), float(ADULT_AGE_MAX), MSG_ADULT_AGE_RANGE)
        if is_teen and age_num is not None:
            _bound(age_num, float(TEEN_MIN_AGE), float(TEEN_MAX_AGE), MSG_TEEN_UI_AGE_RANGE)

        effective_dob = birth_date_parsed or profile.birth_date
        if is_teen:
            if effective_dob is None and (
                request.data.get("current_height_cm") not in (None, "")
                or request.data.get("age") not in (None, "")
            ):
                return Response({"error": MSG_TEEN_REQUIRES_DOB}, status=status.HTTP_400_BAD_REQUEST)
            if effective_dob is not None:
                ae = _age_exact_years(effective_dob)
                if ae < float(TEEN_MIN_AGE) or ae >= float(ADULT_MIN_AGE):
                    return Response({"error": MSG_TEEN_DOB_AGE_RANGE}, status=status.HTTP_400_BAD_REQUEST)

        if is_teen and (
            "father_height_cm" in request.data or "mother_height_cm" in request.data
        ):
            if father_height_cm is None or mother_height_cm is None:
                return Response({"error": MSG_TEEN_REQUIRES_PARENTS}, status=status.HTTP_400_BAD_REQUEST)

        sex = normalize_sex(request.data.get("gender", profile.gender))
        if is_teen and father_height_cm is not None and mother_height_cm is not None:
            if sex not in ("male", "female"):
                return Response(
                    {"error": "Gender (male/female) is required for the genetic height estimate."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            mph_cm = compute_mph_simple_cm(sex, father_height_cm, mother_height_cm)
            if mph_cm < MPH_SIMPLE_CM_MIN or mph_cm > MPH_SIMPLE_CM_MAX:
                return Response({"error": MSG_MPH_OUT_OF_RANGE}, status=status.HTTP_400_BAD_REQUEST)

        if is_teen:
            outlier_reasons = []
            if current_height_cm is not None and (current_height_cm < 120.0 or current_height_cm > 220.0):
                outlier_reasons.append("teen_current_height_extreme")
            if father_height_cm is not None and father_height_cm > 220.0:
                outlier_reasons.append("father_height_extreme")
            if mother_height_cm is not None and mother_height_cm > 220.0:
                outlier_reasons.append("mother_height_extreme")
            if father_height_cm is not None and mother_height_cm is not None:
                if abs(father_height_cm - mother_height_cm) > 35.0:
                    outlier_reasons.append("parent_height_gap_extreme")
            if current_height_cm is not None and father_height_cm is not None and mother_height_cm is not None:
                min_parent = min(father_height_cm, mother_height_cm)
                max_parent = max(father_height_cm, mother_height_cm)
                if current_height_cm < (min_parent - 55.0):
                    outlier_reasons.append("teen_height_far_below_parents")
                if current_height_cm > (max_parent + 20.0):
                    outlier_reasons.append("teen_height_far_above_parents")
            if mph_cm is not None and current_height_cm is not None:
                if abs(current_height_cm - mph_cm) > 40.0:
                    outlier_reasons.append("teen_height_vs_mph_gap_extreme")

            if outlier_reasons and not confirm_outlier:
                # Keep payload shape: return human-readable reasons directly.
                _reason_map = {
                    "teen_current_height_extreme": "Current height looks extreme for a teen (outside 120–220 cm).",
                    "father_height_extreme": "Father's height looks unusually high (over 220 cm).",
                    "mother_height_extreme": "Mother's height looks unusually high (over 220 cm).",
                    "parent_height_gap_extreme": "The difference between parents' heights is unusually large (over 35 cm).",
                    "teen_height_far_below_parents": "Teen height is far below parents' heights (more than 55 cm below the shorter parent).",
                    "teen_height_far_above_parents": "Teen height is far above parents' heights (more than 20 cm above the taller parent).",
                    "teen_height_vs_mph_gap_extreme": "Teen height differs greatly from the genetic estimate (MPH) (more than 40 cm).",
                }
                outlier_reasons = [_reason_map.get(code, code) for code in outlier_reasons]
                return Response(
                    {
                        "error": "outlier_confirmation_required",
                        "message": (
                            "Entered values look unusually extreme. "
                            "If this is correct, resubmit with confirm_outlier=true."
                        ),
                        "requires_confirmation": True,
                        "outlier_reasons": outlier_reasons,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        # Base height lock (spec): immutable after onboarding is complete.
        # Practical exception: allow correction during onboarding steps before the account has any height ledger
        # entries (and before any scan is completed), because onboarding is multi-step.
        if request.data.get("current_height_cm") is not None and str(profile.base_height_cm or "").strip() != "":
            base_f = _as_float(profile.base_height_cm, "base_height_cm")
            new_f = _as_float(request.data.get("current_height_cm"), "current_height_cm")
            if new_f is not None and base_f is not None and abs(new_f - base_f) > 0.01:
                from users.models import HeightLedger, PostureState

                def _step_num(val):
                    try:
                        return int(str(val).strip())
                    except Exception:
                        return None

                req_step = _step_num(request.data.get("profile_step"))
                user_step = _step_num(getattr(user, "profile_step", None))
                onboarding_incomplete = (
                    (req_step is not None and req_step < 3)
                    or (user_step is not None and user_step < 3)
                    or (req_step is None and user_step is None)
                )
                has_ledger = HeightLedger.objects.filter(user=user, entry_type="daily_compute").exists()
                posture_state = PostureState.objects.filter(user=user).first()
                has_scan = bool(posture_state and posture_state.scan_completed)

                if onboarding_incomplete and (not has_ledger) and (not has_scan):
                    # Allow correction: keep base_height_cm synced to the corrected onboarding height.
                    profile.base_height_cm = str(round(new_f, 4))
                else:
                    return Response({"error": MSG_BASE_HEIGHT_LOCKED}, status=status.HTTP_400_BAD_REQUEST)

    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    model_fields = [field.name for field in profile._meta.fields]
    protected_fields = ["id", "user", "base_height_cm"]
    allowed_fields = [f for f in model_fields if f not in protected_fields]

    for key, value in request.data.items():
        if key == "birth_date" and birth_date_parsed is not None:
            value = birth_date_parsed
        if key in allowed_fields:
            setattr(profile, key, value)

    profile.save()

    if profile.base_height_cm in (None, "") and profile.current_height_cm not in (None, ""):
        try:
            ch = float(profile.current_height_cm)
            if USER_HEIGHT_CM_MIN <= ch <= USER_HEIGHT_CM_MAX:
                profile.base_height_cm = str(round(ch, 4))
                profile.save(update_fields=["base_height_cm"])
        except (TypeError, ValueError):
            pass

    if not getattr(user, "account_tier", None):
        if age_num is not None:
            if TEEN_MIN_AGE <= age_num <= TEEN_MAX_AGE:
                user.account_tier = "teen"
                user.save(update_fields=["account_tier"])
            elif age_num >= ADULT_MIN_AGE:
                user.account_tier = "adult"
                user.save(update_fields=["account_tier"])
        elif profile.birth_date or birth_date_parsed:
            dob1 = profile.birth_date or birth_date_parsed
            ae1 = (date.today() - dob1).days / 365.2425
            if TEEN_MIN_AGE <= ae1 < ADULT_MIN_AGE:
                user.account_tier = "teen"
                user.save(update_fields=["account_tier"])
            elif ae1 >= ADULT_MIN_AGE:
                user.account_tier = "adult"
                user.save(update_fields=["account_tier"])

    if 'profile_step' in request.data:
        user.profile_step = request.data['profile_step']
        user.save()

    profile_data = model_to_dict(profile)
    onboarding_extra = {}
    sex_r = normalize_sex(profile.gender)
    fh = None
    mh = None
    if profile.father_height_cm not in (None, ""):
        try:
            fh = float(profile.father_height_cm)
        except (TypeError, ValueError):
            fh = None
    if profile.mother_height_cm not in (None, ""):
        try:
            mh = float(profile.mother_height_cm)
        except (TypeError, ValueError):
            mh = None
    if sex_r in ("male", "female") and fh is not None and mh is not None:
        try:
            onboarding_extra["mph_simple_cm"] = round(compute_mph_simple_cm(sex_r, fh, mh), 2)
        except (TypeError, ValueError):
            pass
    if profile.base_height_cm not in (None, ""):
        try:
            onboarding_extra["base_height_cm"] = float(profile.base_height_cm)
        except (TypeError, ValueError):
            onboarding_extra["base_height_cm"] = profile.base_height_cm
    if confirm_outlier:
        onboarding_extra["outlier_confirmation_used"] = True

    return Response({
        'message': 'Profile updated successfully',
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'profile_step': getattr(user, 'profile_step', None),
            'account_tier': getattr(user, "account_tier", None),
            'profile': profile_data,
            **onboarding_extra,
        }
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([AllowAny])
def check_anormal(request):
    """
    Authenticated helper endpoint: compute teen outlier / abnormal reasons WITHOUT saving.

    Route: POST /api/check-anormal

    Input (JSON):
      - sex or gender: "male" | "female"
      - father_height_cm: number
      - mother_height_cm: number
      - current_height_cm: number
      - age: number (optional; if omitted, checks still run on provided values)

    Output:
      - mph_simple_cm (if computable)
      - outlier_reasons []
      - requires_confirmation bool
      - message (human readable)
    """

    def _as_float(value, field_name):
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be numeric.")

    def _normalize_sex(value):
        raw = (value or "").strip().lower()
        if raw in {"m", "male", "man", "boy"}:
            return "male"
        if raw in {"f", "female", "woman", "girl"}:
            return "female"
        return raw

    try:
        sex = _normalize_sex(request.data.get("sex") or request.data.get("gender"))
        father_cm = _as_float(request.data.get("father_height_cm"), "father_height_cm")
        mother_cm = _as_float(request.data.get("mother_height_cm"), "mother_height_cm")
        current_cm = _as_float(request.data.get("current_height_cm"), "current_height_cm")
        age_num = _as_float(request.data.get("age"), "age") if "age" in request.data else None
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    outlier_reasons = []
    mph_cm = None

    # Compute MPH (spec §2.2 / §5.6 Step 1).
    if sex in {"male", "female"} and father_cm is not None and mother_cm is not None:
        if sex == "male":
            mph_cm = (father_cm + mother_cm + 13.0) / 2.0
        else:
            mph_cm = (father_cm + mother_cm - 13.0) / 2.0

    # Abnormal / outlier rules (mirrors update_profile_users teen outlier checks).
    # Note: this endpoint is intentionally "pure"; it does not infer tier or enforce DOB rules.
    if current_cm is not None and (current_cm < 120.0 or current_cm > 220.0):
        outlier_reasons.append("teen_current_height_extreme")
    if father_cm is not None and father_cm > 220.0:
        outlier_reasons.append("father_height_extreme")
    if mother_cm is not None and mother_cm > 220.0:
        outlier_reasons.append("mother_height_extreme")
    if father_cm is not None and mother_cm is not None:
        if abs(father_cm - mother_cm) > 35.0:
            outlier_reasons.append("parent_height_gap_extreme")
    if current_cm is not None and father_cm is not None and mother_cm is not None:
        min_parent = min(father_cm, mother_cm)
        max_parent = max(father_cm, mother_cm)
        if current_cm < (min_parent - 55.0):
            outlier_reasons.append("teen_height_far_below_parents")
        if current_cm > (max_parent + 20.0):
            outlier_reasons.append("teen_height_far_above_parents")
    if mph_cm is not None and current_cm is not None:
        if abs(current_cm - mph_cm) > 40.0:
            outlier_reasons.append("teen_height_vs_mph_gap_extreme")

    requires_confirmation = bool(outlier_reasons)
    if requires_confirmation:
        message = (
            "Entered values look unusually extreme. "
            "If this is correct, submit onboarding with confirmation."
        )
    else:
        message = "Values look within expected ranges. No outlier confirmation needed."

    # Keep payload shape: return human-readable reasons directly.
    _reason_map = {
        "teen_current_height_extreme": "Current height looks extreme for a teen (outside 120–220 cm).",
        "father_height_extreme": "Father's height looks unusually high (over 220 cm).",
        "mother_height_extreme": "Mother's height looks unusually high (over 220 cm).",
        "parent_height_gap_extreme": "The difference between parents' heights is unusually large (over 35 cm).",
        "teen_height_far_below_parents": "Teen height is far below parents' heights (more than 55 cm below the shorter parent).",
        "teen_height_far_above_parents": "Teen height is far above parents' heights (more than 20 cm above the taller parent).",
        "teen_height_vs_mph_gap_extreme": "Teen height differs greatly from the genetic estimate (MPH) (more than 40 cm).",
    }
    outlier_reasons = [_reason_map.get(code, code) for code in outlier_reasons]
    payload = {
        "sex": sex or None,
        "age": age_num,
        "father_height_cm": father_cm,
        "mother_height_cm": mother_cm,
        "current_height_cm": current_cm,
        "mph_simple_cm": round(float(mph_cm), 2) if mph_cm is not None else None,
        "outlier_reasons": outlier_reasons,
        "requires_confirmation": requires_confirmation,
        "message": message,
    }
    return Response(payload, status=status.HTTP_200_OK)

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
        logger.exception("Stripe response to_dict() failed", extra={"raw_type": type(raw_response).__name__})

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

        profile = UserProfile.objects.filter(user=request.user).first()

        return Response({
            'message': 'Payment verified and saved successfully',
            'payment_status': intent.status,
            'age': age,
            'g_p_facial_armpit_hair': getattr(profile, "g_p_facial_armpit_hair", None)
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

    profile = None
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

    onboarding_read = {}
    if profile is not None:
        sex_r = normalize_sex(profile.gender)
        fh = mh = None
        if profile.father_height_cm not in (None, ""):
            try:
                fh = float(profile.father_height_cm)
            except (TypeError, ValueError):
                pass
        if profile.mother_height_cm not in (None, ""):
            try:
                mh = float(profile.mother_height_cm)
            except (TypeError, ValueError):
                pass
        if sex_r in ("male", "female") and fh is not None and mh is not None:
            try:
                onboarding_read["mph_simple_cm"] = round(compute_mph_simple_cm(sex_r, fh, mh), 2)
            except (TypeError, ValueError):
                pass
        if profile.base_height_cm not in (None, ""):
            try:
                onboarding_read["base_height_cm"] = float(profile.base_height_cm)
            except (TypeError, ValueError):
                onboarding_read["base_height_cm"] = profile.base_height_cm

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
            'account_tier': getattr(user, "account_tier", None),
            'profile': profile_data,
            'profile_type': profile_type_data,
            'current_package': current_package,
            'subscription': subscription_data,
            **onboarding_read,
        }
    }, status=status.HTTP_200_OK)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def my_profile(request):
    """
    Spec-aligned lightweight profile endpoint.

    - GET: return core profile fields used by onboarding + ProfileTab (Section 2 / 12.4 / 13.2 / 16).
    - POST: allow updating *profile settings* (display_name/avatar_url/timezone) and onboarding inputs,
      while keeping Base Height (base_height_cm) read-only once set.

    IMPORTANT: Unlike `get_profile`, this endpoint does NOT block when subscription is expired.
    """
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)

    def _as_float(v):
        if v in (None, ""):
            return None
        try:
            return float(v)
        except Exception:
            return None

    # POST updates (minimal + safe)
    if request.method == "POST":
        # Base height must be immutable once set (Spec Section 2).
        if "base_height_cm" in request.data and str(profile.base_height_cm or "").strip() != "":
            return Response({"error": MSG_BASE_HEIGHT_LOCKED}, status=422)

        def _age_exact_years(dob: date) -> float:
            return (date.today() - dob).days / 365.2425

        def _bound(value, lo, hi, message):
            if value is None:
                return
            if value < lo or value > hi:
                raise ValueError(message)

        # Determine teen/adult rules (same approach as update_profile_users).
        age_num = _as_float(request.data.get("age", profile.age))
        birth_date_candidate = profile.birth_date
        raw_bd = request.data.get("birth_date")
        if raw_bd not in (None, ""):
            try:
                birth_date_candidate = datetime.strptime(str(raw_bd).strip()[:10], "%Y-%m-%d").date()
            except ValueError:
                return Response({"error": "birth_date must be YYYY-MM-DD."}, status=422)

        tier = (getattr(user, "account_tier", None) or "").strip().lower()
        if tier == "teen":
            is_teen = True
        elif tier == "adult":
            is_teen = False
        else:
            if age_num is not None:
                is_teen = TEEN_MIN_AGE <= age_num <= TEEN_MAX_AGE
            elif birth_date_candidate:
                ae0 = _age_exact_years(birth_date_candidate)
                is_teen = TEEN_MIN_AGE <= ae0 < ADULT_MIN_AGE
            else:
                is_teen = False

        # User-level fields (Spec 13.2: display_name, avatar_url, timezone).
        if "display_name" in request.data:
            user.display_name = str(request.data.get("display_name") or "").strip() or None
        if "avatar_url" in request.data:
            user.avatar_url = str(request.data.get("avatar_url") or "").strip() or None
        if "timezone" in request.data:
            tz = str(request.data.get("timezone") or "").strip()
            if tz:
                user.timezone = tz

        # Profile-level onboarding fields (reuse same validation constants as update_profile_users).
        if "gender" in request.data:
            profile.gender = str(request.data.get("gender") or "").strip() or profile.gender
        if "age" in request.data:
            profile.age = str(request.data.get("age") or "").strip() or profile.age
        if "birth_date" in request.data:
            raw_bd = request.data.get("birth_date")
            if raw_bd in (None, ""):
                profile.birth_date = None
            else:
                try:
                    profile.birth_date = datetime.strptime(str(raw_bd).strip()[:10], "%Y-%m-%d").date()
                except ValueError:
                    return Response({"error": "birth_date must be YYYY-MM-DD."}, status=422)

        for k in ("current_height_cm", "father_height_cm", "mother_height_cm"):
            if k in request.data:
                setattr(profile, k, str(request.data.get(k) or "").strip() or None)

        # Section 12.4 bounds (enforced on write)
        try:
            ch = _as_float(profile.current_height_cm)
            fh = _as_float(profile.father_height_cm)
            mh = _as_float(profile.mother_height_cm)
            _bound(ch, USER_HEIGHT_CM_MIN, USER_HEIGHT_CM_MAX, MSG_USER_HEIGHT_RANGE)
            _bound(fh, PARENT_HEIGHT_CM_MIN, PARENT_HEIGHT_CM_MAX, MSG_FATHER_HEIGHT_RANGE)
            _bound(mh, PARENT_HEIGHT_CM_MIN, PARENT_HEIGHT_CM_MAX, MSG_MOTHER_HEIGHT_RANGE)

            if not is_teen and age_num is not None:
                _bound(age_num, float(ADULT_MIN_AGE), float(ADULT_AGE_MAX), MSG_ADULT_AGE_RANGE)
            if is_teen and age_num is not None:
                _bound(age_num, float(TEEN_MIN_AGE), float(TEEN_MAX_AGE), MSG_TEEN_UI_AGE_RANGE)

            # Teen onboarding constraints: DOB and parent heights are required once onboarding inputs are provided.
            effective_dob = profile.birth_date
            if is_teen:
                if effective_dob is None and any(
                    request.data.get(k) not in (None, "") for k in ("current_height_cm", "age", "father_height_cm", "mother_height_cm")
                ):
                    return Response({"error": MSG_TEEN_REQUIRES_DOB}, status=422)
                if (fh is None or mh is None) and any(
                    request.data.get(k) not in (None, "") for k in ("current_height_cm", "age", "birth_date")
                ):
                    return Response({"error": MSG_TEEN_REQUIRES_PARENTS}, status=422)
        except ValueError as e:
            return Response({"error": str(e)}, status=422)

        # Allow first-time base height set from current height (onboarding convenience)
        if str(profile.base_height_cm or "").strip() == "" and str(profile.current_height_cm or "").strip() != "":
            try:
                ch0 = float(profile.current_height_cm)
                if USER_HEIGHT_CM_MIN <= ch0 <= USER_HEIGHT_CM_MAX:
                    profile.base_height_cm = str(round(ch0, 4))
            except Exception:
                logger.exception("Failed setting base_height_cm from current_height_cm", extra={"user_id": getattr(request.user, "id", None)})

        user.save()
        profile.save()

    # --- subscription / plan (never blocks this endpoint) ---
    sex = normalize_sex(profile.gender)
    fh = _as_float(profile.father_height_cm)
    mh = _as_float(profile.mother_height_cm)
    mph_simple_cm = None
    if sex in ("male", "female") and fh is not None and mh is not None:
        try:
            mph_simple_cm = round(compute_mph_simple_cm(sex, fh, mh), 2)
        except Exception:
            mph_simple_cm = None

    base_height_cm = _as_float(profile.base_height_cm)
    current_height_cm = _as_float(profile.current_height_cm)

    subscription_data = {}
    try:
        subscription_data = check_subscription_or_response(user).data
    except Exception:
        subscription_data = {}

    # --- live runtime state (spec-style) ---
    runtime_state = {}
    try:
        runtime_state = get_user_runtime_state_snapshot(user) or {}
    except Exception:
        runtime_state = {}

    # --- today log + points ---
    from utils.user_time import user_today

    today = user_today(user)
    daily = DailyLog.objects.filter(user=user, log_date=today).first()
    today_log = {
        "log_date": str(today),
        "posture_pts": int((daily.engine1_points if daily else 0) or 0),
        "hgh_pts": int((daily.engine2_points if daily else 0) or 0),
        "nutrition_pts": int((daily.food_points if daily else 0) or 0),
        "lifestyle_pts": int((daily.lifestyle_points if daily else 0) or 0),
        "validated": bool(daily.validated) if daily else False,
    }

    totals = DailyLog.objects.filter(user=user).aggregate(
        exercise=Sum("exercise_points"),
        food=Sum("food_points"),
        lifestyle=Sum("lifestyle_points"),
    )
    all_time_points = int((totals.get("exercise") or 0) + (totals.get("food") or 0) + (totals.get("lifestyle") or 0))

    # --- streaks + leaderboard snapshot ---
    streaks = {}
    try:
        streaks = get_user_streaks(user, subscription_data) or {}
    except Exception:
        streaks = {}

    # --- streak history (simple calendar list of last N days) ---
    days_window = 60
    history_rows = (
        DailyLog.objects.filter(user=user)
        .order_by("-log_date")
        .values("log_date", "validated")[:days_window]
    )
    streak_history = [{"date": str(r["log_date"]), "validated": bool(r["validated"])} for r in history_rows]

    # --- my plan (active routines summary) ---
    active_routines = list(
        UserRoutine.objects.filter(user=user, is_active=True).values("id", "routine_type", "created_at")[:10]
    )

    return Response(
        {
            "message": "My profile retrieved successfully" if request.method == "GET" else "My profile updated successfully",
            "data": {
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "account_tier": getattr(user, "account_tier", None),
                    "timezone": getattr(user, "timezone", None),
                    "display_name": getattr(user, "display_name", None),
                    "avatar_url": getattr(user, "avatar_url", None),
                },
                "profile": {
                    "gender": profile.gender,
                    "sex_normalized": sex,
                    "age": profile.age,
                    "birth_date": str(profile.birth_date) if profile.birth_date else None,
                    "current_height_cm": current_height_cm,
                    "base_height_cm": base_height_cm,
                    "father_height_cm": fh,
                    "mother_height_cm": mh,
                },
                "mph_simple_cm": mph_simple_cm,
                "subscription": subscription_data,
                "runtime_state": runtime_state,
                "today_log": today_log,
                "all_time_points": all_time_points,
                "streaks": streaks,
                "streak_history": streak_history,
                "my_plan": {
                    "active_routines": active_routines,
                },
            },
        },
        status=status.HTTP_200_OK,
    )

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