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

# Import services
from posture_questions.services.genetic_height_service import GeneticHeightService
from posture_questions.services.posture_analysis_service import PostureAnalysisService
from posture_questions.services.height_helpers import height_str, ft_in_to_cm, fmt_cm
from posture_questions.services.posture_question_service import PostureQuestionService
from posture_questions.services.growth_projection_service import GrowthProjectionService
from posture_questions.services.routine_service import RoutineService
from posture_questions.services.teen_height_optimization_service import TeenHeightOptimizationService
from typing import Dict, Any, List



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upsert_posture_questions(request):
    user = request.user
    profile = UserProfile.objects.get(user=user)
    profile_dict = model_to_dict(profile)
    print('request', request.data)
    
    # Convert and extract safely
    try:
        father_height = float(profile_dict["father_height_cm"])
        mother_height = float(profile_dict["mother_height_cm"])
        gender = profile_dict["gender"]
        current_age = int(profile_dict.get("age"))
        current_height = float(profile_dict.get("current_height_cm"))
    except (TypeError, ValueError, KeyError) as e:
        return Response({'error': f'Invalid profile data: {e}'}, status=status.HTTP_400_BAD_REQUEST)

    # ───── 1. Calculate Estimated Genetic Height using service ─────
    genetic_estimate = GeneticHeightService.upsert_genetic_estimate(
        user=user,
        father_height=father_height,
        mother_height=mother_height,
        gender=gender,
        current_age=current_age,
        current_height=current_height
    )

    # ───── 2. Upsert Posture Questions using service ─────
    posture_question_data, created = PostureQuestionService.upsert_posture_questions(
        user=user,
        request_data=request.data
    )

    message = 'Posture Questions created successfully' if created else 'Posture Questions updated successfully'
    status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK

    return Response({
        'message': message,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'posture_questions': posture_question_data,
            'estimated_genetic_height_cm': genetic_estimate.estimated_height_cm
        }
    }, status=status_code) 

def get_profile_fields(
    profile_dict: Dict[str, Any],
    keys: List[str],
    default: Any = None
) -> Dict[str, Any]:
    """
    Returns selected keys.
    If key missing or value is None/empty, return default.
    """
    result = {}

    for key in keys:
        value = profile_dict.get(key)

        if value is None or value == "":
            result[key] = default
        else:
            result[key] = value

    return result

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_posture_questions(request):
    user = request.user
    rescan = request.query_params.get('rescan')
    gpt_response = None
    user_dict: Dict[str, Any] = model_to_dict(user)
    
    # ── 1. Check subscription ──────────────────────────────
    subscription_status = check_subscription_or_response(user)

    # If subscription expired, return that same Response directly
    if subscription_status.data.get("expired", True):
        return subscription_status  # contains message + 403 status
    
    # ── 2. Fetch profile ──────────────────────────────
    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        return Response({"error": "User profile not found."}, status=404)

    profile_dict: Dict[str, Any] = model_to_dict(profile)

    # ── 3. Fetch latest posture report ─────────────────
    posture_report = PostureReport.objects.filter(user=user).order_by('-created_at').first()

    # ── 4. Genetic Height Estimate using service ─────────────────────
    genetic_estimate = GeneticHeightService.get_or_create_genetic_estimate(user, profile_dict)

    # ── 5. Build height projections using service ─────
    projections = GrowthProjectionService.get_projection_data(genetic_estimate)

    score_summary = get_user_score_summary(user=user)
    today_total_score = get_user_score_summary(user=user, mode="today_total_score")

    date_str = request.query_params.get("date")
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else None
    except ValueError:
        return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

    green_dots = calculate_green_dots(user=user, target_date=target_date)

    # ── 6. Human-readable heights using helpers ──────────────────────
    current_height = height_str(profile_dict.get("current_height_foot"), profile_dict.get("current_height_inch"))
    ideal_height = height_str(profile_dict.get("ideal_height_foot"), profile_dict.get("ideal_height_inch"))
    father_height = height_str(profile_dict.get("father_height_foot"), profile_dict.get("father_height_inch"))
    mother_height = height_str(profile_dict.get("mother_height_foot"), profile_dict.get("mother_height_inch"))

    dad_cm = ft_in_to_cm(profile_dict.get("father_height_foot"), profile_dict.get("father_height_inch"))
    mom_cm = ft_in_to_cm(profile_dict.get("mother_height_foot"), profile_dict.get("mother_height_inch"))

    gender = (profile_dict.get("gender") or "").strip().lower()
    mph_cm = GrowthProjectionService.calculate_mph_cm(dad_cm, mom_cm, gender)
    mph_cm_display = fmt_cm(mph_cm)

    # ── 7. Growth Math using service ─────────────────────────────────
    current_cm = ft_in_to_cm(profile_dict.get("current_height_foot"), profile_dict.get("current_height_inch")) or 0.0
    age_years = int(profile_dict.get("age", 0))
    daily_genetic_cm = PostureAnalysisService.daily_genetic_gain_cm(current_cm, age_years)

    posture_points_today = profile_dict.get("posture_points_today", 0)
    segment_gains_today = PostureAnalysisService.calculate_segment_gains(posture_points_today)

    current_cm_val = float(profile_dict.get("current_height_cm", 0.0))
    estimated_height_user = genetic_estimate.estimated_height_cm
    genetic_diff, genetic_status = GrowthProjectionService.calculate_genetic_status(
        current_cm_val, estimated_height_user
    )

    # ── 8. Posture analysis using service ────────────────────────────
    ai_analysis, optimization_breakdown = PostureAnalysisService.get_posture_analysis(
        user=user,
        profile_dict=profile_dict,
        rescan=rescan
    )

    # ── 9. Final Response ──────────────────────────────
    chart_breakdown = calculate_height_projection(
        current_height, 
        estimated_height_user + 5, 
        estimated_height_user, 
        estimated_height_user - 5, 
        gender
    )
    
    # Only generate new routine if one doesn't exist using service
    RoutineService.ensure_active_routine(user, optimization_breakdown)

    if user.profile_step != "completed":
        user.profile_step = "completed"
        user.save(update_fields=["profile_step"])

    subscription_data = subscription_status.data
    streaks = get_user_streaks(user)    

    # Check paid status
    is_paid = subscription_data.get("is_paid", False)

    # Optimized height (ONLY if paid teen) using service
    age = int(profile.age)
    posture_breakdown = optimization_breakdown
    total_score = score_summary.get("total_score", False)

    teen_profile = map_userprofile_to_teenprofile(profile, posture_breakdown)

    optimized_height_cm = TeenHeightOptimizationService.get_optimized_height(
        profile=teen_profile,
        is_paid=is_paid,
        posture_breakdown=posture_breakdown
    )

    # Call the MAIN utility
    response_data = get_height_view(
        user=user,
        profile=teen_profile,
        is_paid=is_paid,
        optimized_height_cm=optimized_height_cm,
        total_score=total_score
    )


    estimated_genetic_height_cm = estimated_height_user

    optimized_estimated_genetic_height_cm = estimated_genetic_height_cm + 5
    unoptimized_estimated_genetic_height_cm = estimated_genetic_height_cm - 5

    # If user already exceeded optimized ceiling
    if current_cm_val > optimized_estimated_genetic_height_cm:
        estimated_genetic_height_cm = current_cm_val
        optimized_estimated_genetic_height_cm = current_cm_val + 5
        unoptimized_estimated_genetic_height_cm = current_cm_val - 5

    profile_fields = get_profile_fields(profile_dict, ["age", "gender"], default=None)
    total_max_loss = sum(
        segment["max_loss_cm"]
        for segment in optimization_breakdown.values()
    )
    total_current_loss = sum(
        segment["current_loss_cm"]
        for segment in optimization_breakdown.values()
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
            "profile": profile_fields,
            "ai_analysis": ai_analysis,
            "optimization_breakdown": optimization_breakdown,
            "total_max_loss": total_max_loss,
            "total_current_loss": total_current_loss,
            "chart_breakdown": chart_breakdown,
            "growth_projection": {
                "father_height_cm": float(profile_dict.get("father_height_cm", 0.0)),
                "mother_height_cm": float(profile_dict.get("mother_height_cm", 0.0)),
                "current_height_cm": current_cm_val,
                "optimized_estimated_genetic_height_cm": optimized_estimated_genetic_height_cm,
                "estimated_genetic_height_cm": estimated_genetic_height_cm,
                "unoptimized_estimated_genetic_height_cm": unoptimized_estimated_genetic_height_cm,
                "genetic_height_difference": genetic_diff,
                "genetic_status": genetic_status,
                "green_dots": green_dots,
                "growth_projections": projections,
                "score_summary": score_summary,
                "segment_gain_cm": segment_gains_today,
            },
            "streaks": streaks,
            "max_height": 5.3,
            "response_data": response_data
        },
        status=status.HTTP_200_OK,
    )