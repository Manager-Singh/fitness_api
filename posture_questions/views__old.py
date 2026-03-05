from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import PostureQuestion
from user_profile.models import UserProfile
from django.contrib.auth.models import User
from posture.models import PostureReport

import stripe 
from django.conf import settings
from django.forms.models import model_to_dict
import re
import json
from typing import Any, Dict
from utils.chatgpt_service import generate_chatgpt_response
from height_analysis.models import GeneticHeightEstimate, HeightGrowthProjection
from utils.scores_summary import get_user_score_summary
from utils.workout_food_activity_green_dots import calculate_green_dots
from datetime import datetime
from utils.ai_analysis import save_ai_analysis
from posture_analysis.models import UserPosturalOptimizationData
from posture_analysis.serializers import UserPosturalOptimizationDataSerializer
from utils.posture_optimizer import calculate_optimization_breakdown
from utils.graph_age_projection import calculate_height_projection

from django.utils import timezone
from utils.fcm import send_push_fcm
from utils.routine_genrate import generate_user_routines

from workouts.models import (
    UserRoutine, UserRoutineExercise,
    VariantExercise, RoutineVariant, AgeBracket,
    Tier, Type, Track, Exercise
)
from utils.check_payment import check_subscription_or_response
from utils.streaks import get_user_streaks

from utils.posture.height_access_utility import get_height_view
from utils.teen_optimized_height import compute_optimized_height
from utils.posture.teen_profile_mapper import map_userprofile_to_teenprofile



# ────────────────────────────────────────────────────────────────────────────
# 📍  UNIVERSAL HELPERS
# ────────────────────────────────────────────────────────────────────────────
def height_str(ft: int | None, inch: int | None) -> str:
    """Return `5'11"` or 'unknown' if both parts missing."""
    if ft is None and inch is None:
        return "unknown"
    ft = ft or 0
    inch = inch or 0
    return f"{ft}'{inch}\""


def ft_in_to_cm(ft: int | str | None, inch: int | str | None) -> float | None:
    """Feet+inches → centimetres (None- and str-safe)."""
    if ft is None and inch is None:
        return None
    try:
        ft = float(ft or 0)
        inch = float(inch or 0)
        return ft * 30.48 + inch * 2.54
    except (ValueError, TypeError):
        return None  # gracefully handle invalid input


def fmt_cm(val: float | None) -> str:
    """Return '175.4 cm' or 'unknown'."""
    return f"{val:.1f} cm" if val is not None else "unknown"


# ────────────────────────────────────────────────────────────────────────────
# 📍  GROWTH & POSTURE-GAIN CONSTANTS + HELPERS
# ────────────────────────────────────────────────────────────────────────────
# Annual genetic growth percent for age→age+1 (teen chart)
AGE_GROWTH: Dict[int, float] = {
    13: 0.0450,  # 4.50 %
    14: 0.0325,
    15: 0.0225,
    16: 0.0175,
    17: 0.0125,
    18: 0.0075,
    19: 0.0030,
    20: 0.0020,
}

def annual_growth_percent(age: int) -> float:
    return AGE_GROWTH.get(age, 0.0)

def daily_genetic_gain_cm(height_cm: float, age: int) -> float:
    return height_cm * annual_growth_percent(age) / 365.0

# Share of posture gains per segment
POSTURE_SEGMENT_SPLIT: Dict[str, float] = {
    "spinal_compression": 0.30,
    "posture_collapse":   0.35,
    "pelvic_tilt_back":   0.25,
    "leg_hamstring":      0.10,
}

def posture_gain_cm_from_points(points: int | float) -> float:
    return points * 0.001          # 1 point  = 0.001 cm

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upsert_posture_questions(request):
    user = request.user
    profile = UserProfile.objects.get(user=user)
    profile_dict = model_to_dict(profile)
    print('request',request.data)
    # Convert and extract safely
    try:
        father_height = float(profile_dict["father_height_cm"])
        mother_height = float(profile_dict["mother_height_cm"])
        gender = profile_dict["gender"]
        current_age = int(profile_dict.get("age"))
        current_height = float(profile_dict.get("current_height_cm"))
    except (TypeError, ValueError, KeyError) as e:
        return Response({'error': f'Invalid profile data: {e}'}, status=status.HTTP_400_BAD_REQUEST)

    # ───── 1. Calculate Estimated Genetic Height ─────
    def calculate_estimated_genetic_height(father_cm, mother_cm, gender):
        avg = (father_cm + mother_cm) / 2
        return round(avg + 6.5, 2) if gender.lower() == 'male' else round(avg - 6.5, 2)

    estimated_height = calculate_estimated_genetic_height(father_height, mother_height, gender)

    # Save to GeneticHeightEstimate
    genetic_estimate, _ = GeneticHeightEstimate.objects.update_or_create(
        user=user,
        defaults={'estimated_height_cm': estimated_height}
    )

    # ───── 2. Create Growth Projections ─────
    growth_brackets = [
        (13, 14, 0.045, 0.0018),
        (14, 15, 0.0325, 0.0014),
        (15, 16, 0.0225, 0.0011),
        (16, 17, 0.0175, 0.0008),
        (17, 18, 0.0125, 0.0005),
        (18, 19, 0.0075, 0.0003),
        (19, 20, 0.003,  0.0002),
        (20, 21, 0.002,  0.0001),
    ]

    genetic_estimate.growth_projections.all().delete()

    if current_age > 21:
        HeightGrowthProjection.objects.create(
            genetic_estimate=genetic_estimate,
            current_age=current_age,
            current_height_cm=current_height,
            age_range="21+",
            annual_growth_percent=0.0,
            estimated_annual_gain_cm=0.0,
            estimated_daily_gain_cm=0.0,
        )
    else:
        for min_age, max_age, percent, _ in growth_brackets:
            if min_age <= current_age < max_age:
                gain_cm = estimated_height * percent
                HeightGrowthProjection.objects.create(
                    genetic_estimate=genetic_estimate,
                    current_age=current_age,
                    current_height_cm=current_height,
                    age_range=f"{min_age}-{max_age}",
                    annual_growth_percent=percent,
                    estimated_annual_gain_cm=round(gain_cm, 2),
                    estimated_daily_gain_cm=round(gain_cm / 365, 4),
                )
                break

    # ───── 3. Upsert Posture Questions ─────
    allowed_fields = [
        'forward_head_posture_question',
        'forward_head_posture_options',
        'forward_head_posture_answer',
        'gap_between_your_lower_back_question',
        'gap_between_your_lower_back_options',
        'gap_between_your_lower_back_answer',
        'tightness_or_discomfort_question',
        'tightness_or_discomfort_options',
        'tightness_or_discomfort_answer',
        'slouch_when_standing_or_sitting_question',
        'slouch_when_standing_or_sitting_options',
        'slouch_when_standing_or_sitting_answer',
        'feel_noticeably_shorter_end_of_day_compare_to_morning_question',
        'feel_noticeably_shorter_end_of_day_compare_to_morning_options',
        'feel_noticeably_shorter_end_of_day_compare_to_morning_answer',
        'perfectly_aligned_and_decompressed_question',
        'perfectly_aligned_and_decompressed_options',
        'perfectly_aligned_and_decompressed_answer',
        'flexible_in_your_hamstrings_and_hips_question',
        'flexible_in_your_hamstrings_and_hips_options',
        'flexible_in_your_hamstrings_and_hips_answer',
        'active_your_core_during_daily_task_question',
        'active_your_core_during_daily_task_options',
        'active_your_core_during_daily_task_answer',
    ]

    update_data = {field: request.data[field] for field in allowed_fields if field in request.data}

    posture_question, created = PostureQuestion.objects.update_or_create(
        user=user,
        defaults=update_data
    )

    posture_question_data = model_to_dict(posture_question)
    message = 'Posture Questions created successfully' if created else 'Posture Questions updated successfully'
    status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK

    return Response({
        'message': message,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'posture_questions': posture_question_data,
            'estimated_genetic_height_cm': estimated_height
        }
    }, status=status_code) 

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_posture_questions(request):
    user = request.user
    rescan = request.query_params.get('rescan')
    gpt_response = None
    user_dict: Dict[str, Any] = model_to_dict(user)
    # result = send_push_fcm(user.fcm_token, 'Helli', 'This Push Notification')
    # ── 1. Fetch profile ──────────────────────────────
    # subscription_status = check_subscription_or_response(user)
    # if subscription_status.data["expired"]:   # always available now
    #     return subscription_status  # returns Response with 403
    # 🔍 Check user's current subscription
    subscription_status = check_subscription_or_response(user)

    # 🧩 If subscription expired, return that same Response directly
    if subscription_status.data.get("expired", True):
        return subscription_status  # contains message + 403 status
    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        return Response({"error": "User profile not found."}, status=404)

    profile_dict: Dict[str, Any] = model_to_dict(profile)

    # ── 2. Fetch latest posture report ─────────────────
    posture_report = PostureReport.objects.filter(user=user).order_by('-created_at').first()

    # ── 3. Genetic Height Estimate ─────────────────────
    try:
        genetic_estimate = GeneticHeightEstimate.objects.prefetch_related('growth_projections').get(user=user)
    except GeneticHeightEstimate.DoesNotExist:
        # Defensive field extraction
        try:
            father_cm = float(profile_dict.get("father_height_cm", 0.0))
            mother_cm = float(profile_dict.get("mother_height_cm", 0.0))
            gender = (profile_dict.get("gender") or "").strip().lower()
            current_age = int(profile_dict.get("age", 0))
            current_height = float(profile_dict.get("current_height_cm", 0.0))
        except (ValueError, TypeError):
            return Response({"error": "Invalid data in profile for genetic calculation."}, status=400)

        def calculate_estimated_genetic_height(father_cm, mother_cm, gender):
            avg = (father_cm + mother_cm) / 2
            return round(avg + 6.5, 2) if gender == 'male' else round(avg - 6.5, 2)

        estimated_height = calculate_estimated_genetic_height(father_cm, mother_cm, gender)

        genetic_estimate = GeneticHeightEstimate.objects.create(
            user=user,
            estimated_height_cm=estimated_height
        )

        # Growth brackets
        if gender == "male":
            age_check = 21
            growth_brackets = [
                (13, 14, 0.036), (14, 15, 0.026), (15, 16, 0.019), (16, 17, 0.0155),
                (17, 18, 0.011), (18, 19, 0.0075), (19, 20, 0.003), (20, 21, 0.002),
            ]
        else:
            age_check = 17
            growth_brackets = [
                (13, 14, 0.0225), (14, 15, 0.0125), (15, 16, 0.004), (16, 17, 0.001),
            ]

        # Save projection if needed
        if current_age and current_height:
            if current_age > age_check:
                HeightGrowthProjection.objects.create(
                    genetic_estimate=genetic_estimate,
                    current_age=current_age,
                    current_height_cm=current_height,
                    age_range="21+",
                    annual_growth_percent=0.0,
                    estimated_annual_gain_cm=0.0,
                    estimated_daily_gain_cm=0.0,
                )
            else:
                for min_age, max_age, percent in growth_brackets:
                    if min_age <= current_age < max_age:
                        gain_cm = estimated_height * percent
                        HeightGrowthProjection.objects.create(
                            genetic_estimate=genetic_estimate,
                            current_age=current_age,
                            current_height_cm=current_height,
                            age_range=f"{min_age}-{max_age}",
                            annual_growth_percent=percent,
                            estimated_annual_gain_cm=round(gain_cm, 2),
                            estimated_daily_gain_cm=round(gain_cm / 365, 4),
                        )
                        break

    # ── 4. Build height projections and green dots ─────
    projections = None
    first_projection = genetic_estimate.growth_projections.first()
    if first_projection:
        projections = {
            'age_range': first_projection.age_range,
            'annual_growth_percent': first_projection.annual_growth_percent,
            'estimated_annual_gain_cm': first_projection.estimated_annual_gain_cm,
            'estimated_daily_gain_cm': first_projection.estimated_daily_gain_cm,
        }

    score_summary = get_user_score_summary(user=user)
    today_total_score = get_user_score_summary(user=user, mode="today_total_score")

    date_str = request.query_params.get("date")
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else None
    except ValueError:
        return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

    green_dots = calculate_green_dots(user=user, target_date=target_date)

    # ── 5. Human-readable heights ──────────────────────
    current_height = height_str(profile_dict.get("current_height_foot"), profile_dict.get("current_height_inch"))
    ideal_height = height_str(profile_dict.get("ideal_height_foot"), profile_dict.get("ideal_height_inch"))
    father_height = height_str(profile_dict.get("father_height_foot"), profile_dict.get("father_height_inch"))
    mother_height = height_str(profile_dict.get("mother_height_foot"), profile_dict.get("mother_height_inch"))

    dad_cm = ft_in_to_cm(profile_dict.get("father_height_foot"), profile_dict.get("father_height_inch"))
    mom_cm = ft_in_to_cm(profile_dict.get("mother_height_foot"), profile_dict.get("mother_height_inch"))

    gender = (profile_dict.get("gender") or "").strip().lower()
    mph_cm = None
    if dad_cm is not None and mom_cm is not None:
        mph_cm = (dad_cm + mom_cm + 13) / 2 if gender == "male" else (dad_cm + mom_cm - 13) / 2

    mph_cm_display = fmt_cm(mph_cm)

    # ── 6. Growth Math ─────────────────────────────────
    current_cm = ft_in_to_cm(profile_dict.get("current_height_foot"), profile_dict.get("current_height_inch")) or 0.0
    age_years = int(profile_dict.get("age", 0))
    daily_genetic_cm = daily_genetic_gain_cm(current_cm, age_years)

    posture_points_today = profile_dict.get("posture_points_today", 0)
    daily_posture_gain_cm = posture_gain_cm_from_points(posture_points_today)

    segment_gains_today = {
        seg: round(daily_posture_gain_cm * frac, 4)
        for seg, frac in POSTURE_SEGMENT_SPLIT.items()
    }

    current_cm_val = float(profile_dict.get("current_height_cm", 0.0))
    estimated_height_user = genetic_estimate.estimated_height_cm
    genetic_diff = round(current_cm_val - estimated_height_user, 2)
    if genetic_diff > 0:
        genetic_status = "above_estimated_genetic_height"
    elif genetic_diff < 0:
        genetic_status = "below_estimated_genetic_height"
    else:
        genetic_status = "at_estimated_genetic_height"

    # ── 7. Posture analysis ────────────────────────────
    if posture_report and posture_report.data:
        mdata = posture_report.data or {}

        ai_analysis = mdata.get("summary")
        optimization_breakdown = mdata.get("optimization_breakdown")

        # Fallback to nested "analysis" block if top-level keys not found
        if ai_analysis is None or optimization_breakdown is None:
            analysis_data = mdata.get("analysis", {})
            ai_analysis = ai_analysis or analysis_data.get("summary")
            optimization_breakdown = optimization_breakdown or analysis_data.get("optimization_breakdown")
    else:
        posture_q = PostureQuestion.objects.filter(user=user).first()
        if not posture_q:
            return Response({"error": "Posture Question data not found."}, status=404)

        posture_dict: Dict[str, Any] = model_to_dict(posture_q)

        questionnaire_full = {}
        for field, value in posture_dict.items():
            if field.endswith(("_question", "_options", "_answer")):
                base, suffix = field.rsplit("_", 1)
                questionnaire_full.setdefault(base, {})[suffix] = value

        q = posture_dict
        questionnaire_scores = {
            "forward_head_posture": q.get("forward_head_posture_answer"),
            "lower_back_gap":       q.get("gap_between_your_lower_back_answer"),
            "back_tightness":       q.get("tightness_or_discomfort_answer"),
            "slouching":            q.get("slouch_when_standing_or_sitting_answer"),
            "end_of_day_height":    q.get("feel_noticeably_shorter_end_of_day_compare_to_morning_answer"),
            "alignment":            q.get("perfectly_aligned_and_decompressed_answer"),
            "hamstring_flexibility":q.get("flexible_in_your_hamstrings_and_hips_answer"),
            "core_activation":      q.get("active_your_core_during_daily_task_answer"),
        }

        shoe_size_display = profile_dict.get("shoe_size", "not provided")

        #         # ── 6. Build GPT prompt ───────────────────────────────────────────────
        prompt = f"""
        You are a certified physiotherapist and posture expert. Your job is to analyze the user's posture-related questionnaire and physical profile to provide accurate, scientific feedback.

        TASK 1 – Posture Summary and Recommendations  
        Based on the user's answers and profile data:
        • Write a short summary of their posture condition.  
        • Provide 5 personalized recommendations (each with a title and 1-2 sentence description).  
        • Estimate a realistic "max_height_gain_inches" from posture correction alone (typically 0 to 1.5 inches).  
        • Add a short note to remind the user that genetic factors and professional supervision matter.

        TASK 2 – Postural Optimization Breakdown  
        Use the 8 posture-related answers (SECOND JSON block) to assign scores from 0–100 (where 100 = major issue and 0 = no issue) for:
        1. spinal_compression  
        2. posture_collapse  
        3. pelvic_tilt_back  
        4. leg_hamstring  

        Use the meaning or severity of the answers to distribute scores proportionally. For example, "severe slouching" or "constant tightness" should result in a high percentage.

        TASK 3 – Growth Potential Analysis  
        Use the profile data to:
        • Estimate the user's **daily genetic growth potential (cm/day)** based on age and current height.  
        • Estimate their **daily posture-based gain (cm/day)** using posture_points_today.  
        • Break posture-based gain into 4 parts using the segment gain split (see POSTURE SEGMENT SPLIT).

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        QUESTIONNAIRE FULL (question / options / answer):
        {json.dumps(questionnaire_full, indent=2, ensure_ascii=False)}

        POSTURE SCORES (8 answers):
        {json.dumps(questionnaire_scores, indent=2, ensure_ascii=False)}

        PROFILE DATA:
        • Age: {profile_dict['age']} – Gender: {profile_dict['gender']}  
        • Current height: {current_height} – Ideal height: {ideal_height}  
        • Father height: {father_height} – Mother height: {mother_height}  
        • Estimated genetic height: {mph_cm_display}  
        • Weight: {profile_dict['current_weight']} – Shoe size: {shoe_size_display}  
        • Activity level: {profile_dict['activity_level_answer']}  
        • Sitting hours/day: {profile_dict['sitting_hours_answer']}  
        • Sleep: {profile_dict['sleep_quality_and_position_answer_one']} h – \
        Position: {profile_dict['sleep_quality_and_position_answer_two']}  
        • Flexibility: {profile_dict['posture_and_flexibility_answer_one']}, \
        {profile_dict['posture_and_flexibility_answer_two']}, \
        {profile_dict['posture_and_flexibility_answer_three']}  
        • Posture Points Today: {posture_points_today}  

        POSTURE SEGMENT SPLIT (use for gain distribution):
        {json.dumps(POSTURE_SEGMENT_SPLIT, indent=2)}

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        ### OUTPUT FORMAT (JSON only)

        {{
        "summary": "...",
        "recommendations": [
            {{ "title": "...", "description": "..." }}
        ],
        "max_height_gain_inches": 0.0,
        "note": "...",
        "postural_optimization": {{
            "spinal_compression": 0,
            "posture_collapse": 0,
            "pelvic_tilt_back": 0,
            "leg_hamstring": 0
        }}
        }}
        """
        # print('heelo')
        try:
            if rescan == "yes":
                raise UserPosturalOptimizationData.DoesNotExist

            user_data = UserPosturalOptimizationData.objects.get(user=user)
            serializer = UserPosturalOptimizationDataSerializer(user_data)
            ai_analysis = serializer.data
            # print('try \n')

        except UserPosturalOptimizationData.DoesNotExist:
            gpt_response = generate_chatgpt_response(prompt, system_role="You are a health and posture expert.")
            profile.last_scan = timezone.now()
            profile.save()
            # print('except \n')

            if gpt_response:
                user_data = save_ai_analysis(user, gpt_response)
                serializer = UserPosturalOptimizationDataSerializer(user_data)
                ai_analysis = serializer.data
                # print('gpt \n')
            else:
                ai_analysis = None
                # print('gpt else \n')

        optimization_breakdown = calculate_optimization_breakdown(ai_analysis)

    # ── 8. Final Response ──────────────────────────────
    chart_breakdown = calculate_height_projection(
        current_height, 
        estimated_height_user + 5, 
        estimated_height_user, 
        estimated_height_user - 5, 
        gender
    )
    # Check if user already has an active routine
    has_active_routine = UserRoutine.objects.filter(
        user=user,
        is_active=True
    ).exists()
    # print('optimization_breakdown\n')
    # print(optimization_breakdown)
    # Only generate new routine if one doesn't exist
    if not has_active_routine:
        generate_user_routines(user, optimization_breakdown)

    if user.profile_step != "completed":
        user.profile_step = "completed"
        user.save(update_fields=["profile_step"])

    subscription_data = subscription_status.data
    streaks = get_user_streaks(user)    


    # print("subscription_data\n")
    # print(subscription_data)

      # 1️⃣ Fetch profile
    # profile = UserProfile.objects.get(user=user)

    # 2️⃣ Check paid status
    is_paid = subscription_data.get("is_paid", False) # your existing logic

    # 3️⃣ Optimized height (ONLY if paid teen)
    optimized_height_cm = None

    age = int(profile.age)
    # print("posture_report\n")
    # print(posture_report)

    posture_breakdown = optimization_breakdown  # dict

    total_score = score_summary.get("total_score", False)

    teen_profile = map_userprofile_to_teenprofile(
        profile,
        posture_breakdown
    )


  
    if is_paid and 13 <= age <= 20:
        # Run advanced model ONLY for paid teens
        optimized_result = compute_optimized_height(teen_profile)
        optimized_height_cm = optimized_result["optimized_height_cm"]

    # 4️⃣ Call the MAIN utility
    response_data = get_height_view(
        user=user,
        profile=teen_profile,
        is_paid=is_paid,
        optimized_height_cm=optimized_height_cm,
        total_score=total_score
    )

    return Response(
        {
            "message": "Posture Questions retrieved successfully",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            },
            'subscription': subscription_data, 
            "today_total_score": today_total_score,
            "last_scan": profile_dict.get("last_scan"),
            "scan_days": 30,
            "profile": profile_dict,
            "ai_analysis": ai_analysis,
            "optimization_breakdown": optimization_breakdown,
            "chart_breakdown": chart_breakdown,
            "growth_projection": {
                "father_height_cm": float(profile_dict.get("father_height_cm", 0.0)),
                "mother_height_cm": float(profile_dict.get("mother_height_cm", 0.0)),
                "current_height_cm": current_cm_val,
                "optimized_estimated_genetic_height_cm": estimated_height_user + 5,
                "estimated_genetic_height_cm": estimated_height_user,
                "unoptimized_estimated_genetic_height_cm": estimated_height_user - 5,
                "genetic_height_difference": genetic_diff,
                "genetic_status": genetic_status,
                "green_dots": green_dots,
                "growth_projections": projections,
                "score_summary": score_summary,
                "segment_gain_cm": segment_gains_today,
            },
            "streaks":streaks,
            "max_height":5.3,
            "response_data":response_data
        },
        status=status.HTTP_200_OK,
    )