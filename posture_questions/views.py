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
import logging
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
from django.db.models import Sum
from utils.fcm import send_push_fcm
from utils.routine_genrate import generate_user_routines

from workouts.models import (
    UserRoutine, UserRoutineExercise,
    VariantExercise, RoutineVariant, AgeBracket,
    Tier, Type, Track, Exercise, RoutineType, WorkoutEntry, WorkoutSession
)
from utils.check_payment import check_subscription_or_response
from utils.streaks import get_user_streaks

logger = logging.getLogger(__name__)

from utils.posture.height_access_utility import get_height_view
from utils.teen_optimized_height import compute_optimized_height
from utils.posture.teen_profile_mapper import map_userprofile_to_teenprofile
from utils.posture.height_constants import (
    OPTIMIZATION_GAP_CM,
    POINTS_TO_CM_ENGINE1,
    POINTS_TO_CM_ENGINE2,
    POSTURE_BOOST_MAX_CM,
    TOTAL_STRUCTURAL_CEILING_CM,
    UI_TO_CODE_VARIABLE_NAMES,
    default_optimization_breakdown_pending_scan,
)

# Import services
from posture_questions.services.genetic_height_service import GeneticHeightService
from posture_questions.services.posture_analysis_service import PostureAnalysisService
from posture_questions.services.height_helpers import height_str, ft_in_to_cm, fmt_cm
from posture_questions.services.posture_question_service import PostureQuestionService
from posture_questions.services.growth_projection_service import GrowthProjectionService
from posture_questions.services.routine_service import RoutineService
from posture_questions.services.teen_height_optimization_service import TeenHeightOptimizationService
from typing import Dict, Any, List

from datetime import timedelta
from utils.age import get_user_age_exact
from utils.posture.section3_manual_scoring import build_section3_manual_breakdown
from users.spec_runtime import get_user_runtime_state_snapshot, apply_pending_pre_scan_engine1
from users.models import DailyLog, HeightLedger, PostureState
from utils.posture.diagnostics_contract import build_posture_optimization_diagnostics
from utils.monetization_gate import compute_monetization_flags
from nutration.models_log import NutraEntry
from posture_questions.serializers_dashboard import DashboardNewResponseSerializer
from utils.user_time import user_today, user_localize_dt
from utils.teen_dashboard_dots import (
    teen_lifestyle_dots_for_day,
    teen_lifestyle_nutrition_combined_percent,
    teen_nutrition_dots_from_food_points,
)
from utils.posture.teen_genetic_average import (
    compute_daily_genetic_average_gain_cm,
    compute_genetic_average_cm,
)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upsert_posture_questions(request):
    user = request.user
    profile = UserProfile.objects.get(user=user)
    profile_dict = model_to_dict(profile)
    # Convert and extract safely
    try:
        age_exact = float(get_user_age_exact(user) or 0.0)
        current_age = int(age_exact) if age_exact > 0 else int(float(profile_dict.get("age") or 0))
        gender = profile_dict.get("gender")
        base_height = float(profile_dict.get("base_height_cm") or profile_dict.get("current_height_cm") or 0.0)
        current_height = base_height

        father_height = float(profile_dict.get("father_height_cm")) if current_age < 21 else None
        mother_height = float(profile_dict.get("mother_height_cm")) if current_age < 21 else None

    except (TypeError, ValueError, KeyError) as e:
        return Response({'error': f'Invalid profile data: {e}'}, status=status.HTTP_400_BAD_REQUEST)

    is_adult = bool(getattr(user, "account_tier", None) == "adult" or current_age >= 21)
    is_teen = bool(current_age < 21)

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
    # NOTE (product):
    # This backend supports two "scan" sources:
    # - full posture scan (camera) via `posture/views.py` which always updates `last_scan`
    # - manual posture questionnaire (adults) which, once completed, should also stamp `last_scan`
    #   for UX parity (but only when the questionnaire becomes complete, not on every update).


    # Section 3 (v3.3): compute and persist manual questionnaire state (adults + teens).
    section3_contract = None
    posture_q = PostureQuestionService.get_posture_questions(user)
    if posture_q:
        required_answers = [
            posture_q.forward_head_posture_answer,
            posture_q.gap_between_your_lower_back_answer,
            posture_q.tightness_or_discomfort_answer,
            posture_q.slouch_when_standing_or_sitting_answer,
            posture_q.feel_noticeably_shorter_end_of_day_compare_to_morning_answer,
            posture_q.perfectly_aligned_and_decompressed_answer,
            posture_q.flexible_in_your_hamstrings_and_hips_answer,
            posture_q.active_your_core_during_daily_task_answer,
        ]
        questionnaire_complete = all((v is not None and str(v).strip() != "") for v in required_answers)
        state, _ = PostureState.objects.get_or_create(user=user)
        state.questionnaire_completed = questionnaire_complete

        if questionnaire_complete:
            now_ts = timezone.now()
            if state.questionnaire_completed_at is None:
                state.questionnaire_completed_at = now_ts

            # Adults: questionnaire completion is treated as a scan-equivalent unlock and stamps last_scan.
            # Teens (v3.3): questionnaire completion unlocks gains but does not necessarily mean a camera scan exists.
            if is_adult:
                needs_scan_stamp = (
                    (getattr(profile, "last_scan", None) is None)
                    or (state.last_scan_at is None)
                    or (not bool(state.scan_completed))
                )
                if needs_scan_stamp:
                    if getattr(profile, "last_scan", None) is None:
                        profile.last_scan = now_ts
                        profile.save(update_fields=["last_scan"])
                    if state.last_scan_at is None:
                        state.last_scan_at = now_ts
                    state.scan_completed = True
            else:
                # v3.3: Teen trial starts on first unlock (scan OR questionnaire).
                try:
                    age_exact_now = float(get_user_age_exact(user) or 0.0)
                except Exception:
                    age_exact_now = 0.0
                if 13.0 <= age_exact_now < 21.0:
                    if getattr(user, "trial_start", None) is None:
                        user.trial_start = now_ts
                    if getattr(user, "trial_end", None) is None and getattr(user, "trial_start", None) is not None:
                        user.trial_end = user.trial_start + timedelta(days=7)
                    try:
                        user.save(update_fields=["trial_start", "trial_end"])
                    except Exception:
                        logger.exception("Failed saving teen trial_start/trial_end on questionnaire unlock")

            clamp_min = 1.0 if is_adult else 0.0
            manual = build_section3_manual_breakdown(posture_q, clamp_min_cm=clamp_min)
            total_recoverable = float(manual["total_recoverable_loss_cm"])
            target_height = round(base_height + total_recoverable, 2)
            section3_contract = {
                "raw_score_cm": manual["raw_score_cm"],
                "total_recoverable_loss_cm": total_recoverable,
                "distribution_ratio": "30/35/25/10",
                "optimization_breakdown": manual["optimization_breakdown"],
                "target_height_cm": target_height,
                "target_height_formula": "Base_Height + Total_Recoverable_Loss",
            }
            state.total_recoverable_loss_um = int(round(total_recoverable * 10000))
            seg = manual["optimization_breakdown"]
            state.spinal_current_loss_um = int(round(float(seg["spinal_compression"]["current_loss_cm"]) * 10000))
            state.collapse_current_loss_um = int(round(float(seg["posture_collapse"]["current_loss_cm"]) * 10000))
            state.pelvic_current_loss_um = int(round(float(seg["pelvic_tilt_back"]["current_loss_cm"]) * 10000))
            state.legs_current_loss_um = int(round(float(seg["leg_hamstring"]["current_loss_cm"]) * 10000))
            state.save(update_fields=[
                "scan_completed",
                "questionnaire_completed",
                "questionnaire_completed_at",
                "total_recoverable_loss_um",
                "spinal_current_loss_um",
                "collapse_current_loss_um",
                "pelvic_current_loss_um",
                "legs_current_loss_um",
                "last_scan_at",
            ])
            if (not is_adult):
                # v3.3: Apply any pending pre-scan posture gains immediately on questionnaire unlock.
                try:
                    apply_pending_pre_scan_engine1(user, when=user_today(user))
                except Exception:
                    logger.exception(
                        "Failed applying pending_pre_scan engine1 gains after teen questionnaire completion",
                        extra={"user_id": getattr(user, "id", None)},
                    )
                # v3.3: Run exercise assignment pipeline immediately after teen questionnaire unlock.
                try:
                    RoutineService.ensure_active_routine(user, manual["optimization_breakdown"])
                except Exception:
                    logger.exception(
                        "Failed generating teen routine after questionnaire unlock",
                        extra={"user_id": getattr(user, "id", None)},
                    )
        else:
            state.save(update_fields=["questionnaire_completed"])

    subscription_status = check_subscription_or_response(user)

    subscription_data = subscription_status.data
    is_paid = bool(subscription_data.get("is_paid", False))

    message = 'Posture Questions created successfully' if created else 'Posture Questions updated successfully'
    status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK

    state = PostureState.objects.filter(user=user).first()
    return Response({
        'message': message,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'gender':gender,
            'age':current_age,
            'is_paid':is_paid,
            'subscription_data':subscription_data,
            'posture_questions': posture_question_data,
            'estimated_genetic_height_cm': genetic_estimate.estimated_height_cm,
            'section3_contract': section3_contract,
            'last_scan': profile.last_scan.isoformat() if getattr(profile, "last_scan", None) else None,
            'questionnaire_completed': bool(state.questionnaire_completed) if state else False,
            'questionnaire_completed_at': state.questionnaire_completed_at.isoformat() if (state and state.questionnaire_completed_at) else None,
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

# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def get_posture_questions(request):
#     user = request.user
#     rescan = request.query_params.get('rescan')
#     gpt_response = None
#     user_dict: Dict[str, Any] = model_to_dict(user)
    
#     # ── 1. Check subscription ──────────────────────────────
#     subscription_status = check_subscription_or_response(user)

#     # If subscription expired, return that same Response directly
#     if subscription_status.data.get("expired", True):
#         return subscription_status  # contains message + 403 status
    
#     # ── 2. Fetch profile ──────────────────────────────
#     try:
#         profile = UserProfile.objects.get(user=user)
#     except UserProfile.DoesNotExist:
#         return Response({"error": "User profile not found."}, status=404)

#     profile_dict: Dict[str, Any] = model_to_dict(profile)

#     # ── 3. Fetch latest posture report ─────────────────
#     posture_report = PostureReport.objects.filter(user=user).order_by('-created_at').first()

#     # ── 4. Genetic Height Estimate using service ─────────────────────
#     genetic_estimate = GeneticHeightService.get_or_create_genetic_estimate(user, profile_dict)

#     # ── 5. Build height projections using service ─────
#     projections = GrowthProjectionService.get_projection_data(genetic_estimate)

#     score_summary = get_user_score_summary(user=user)
#     today_total_score = get_user_score_summary(user=user, mode="today_total_score")

#     date_str = request.query_params.get("date")
#     try:
#         target_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else None
#     except ValueError:
#         return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

#     green_dots = calculate_green_dots(user=user, target_date=target_date)

#     # ── 6. Human-readable heights using helpers ──────────────────────
#     current_height = height_str(profile_dict.get("current_height_foot"), profile_dict.get("current_height_inch"))
#     ideal_height = height_str(profile_dict.get("ideal_height_foot"), profile_dict.get("ideal_height_inch"))
#     father_height = height_str(profile_dict.get("father_height_foot"), profile_dict.get("father_height_inch"))
#     mother_height = height_str(profile_dict.get("mother_height_foot"), profile_dict.get("mother_height_inch"))

#     dad_cm = ft_in_to_cm(profile_dict.get("father_height_foot"), profile_dict.get("father_height_inch"))
#     mom_cm = ft_in_to_cm(profile_dict.get("mother_height_foot"), profile_dict.get("mother_height_inch"))

#     gender = (profile_dict.get("gender") or "").strip().lower()
#     mph_cm = GrowthProjectionService.calculate_mph_cm(dad_cm, mom_cm, gender)
#     mph_cm_display = fmt_cm(mph_cm)

#     # ── 7. Growth Math using service ─────────────────────────────────
#     current_cm = ft_in_to_cm(profile_dict.get("current_height_foot"), profile_dict.get("current_height_inch")) or 0.0
#     age_years = int(profile_dict.get("age", 0))
#     daily_genetic_cm = PostureAnalysisService.daily_genetic_gain_cm(current_cm, age_years)

#     posture_points_today = profile_dict.get("posture_points_today", 0)
#     segment_gains_today = PostureAnalysisService.calculate_segment_gains(posture_points_today)

#     current_cm_val = float(profile_dict.get("base_height_cm") or profile_dict.get("current_height_cm", 0.0))
#     estimated_height_user = genetic_estimate.estimated_height_cm
#     genetic_diff, genetic_status = GrowthProjectionService.calculate_genetic_status(
#         current_cm_val, estimated_height_user
#     )

#     # ── 8. Posture analysis using service ────────────────────────────
#     ai_analysis, optimization_breakdown = PostureAnalysisService.get_posture_analysis(
#         user=user,
#         profile_dict=profile_dict,
#         rescan=rescan
#     )

#     # ── 9. Final Response ──────────────────────────────
#     chart_breakdown = calculate_height_projection(
#         current_height, 
#         estimated_height_user + 5, 
#         estimated_height_user, 
#         estimated_height_user - 5, 
#         gender
#     )
    
#     # Only generate new routine if one doesn't exist using service
#     RoutineService.ensure_active_routine(user, optimization_breakdown)

#     if user.profile_step != "completed":
#         user.profile_step = "completed"
#         user.save(update_fields=["profile_step"])

#     subscription_data = subscription_status.data
#     streaks = get_user_streaks(user)    

#     # Check paid status
#     is_paid = subscription_data.get("is_paid", False)

#     # Optimized height (ONLY if paid teen) using service
#     age = int(profile.age)
#     posture_breakdown = optimization_breakdown
#     total_score = score_summary.get("total_score", False)

#     # teen_profile = map_userprofile_to_teenprofile(profile, posture_breakdown)
#     # print(teen_profile)

#     optimized_height_cm = TeenHeightOptimizationService.get_optimized_height(
#         profile=teen_profile,
#         is_paid=is_paid,
#         posture_breakdown=posture_breakdown
#     )

#     # Call the MAIN utility
#     response_data = get_height_view(
#         user=user,
#         profile=teen_profile,
#         is_paid=is_paid,
#         optimized_height_cm=optimized_height_cm,
#         total_score=total_score
#     )


#     estimated_genetic_height_cm = estimated_height_user

#     optimized_estimated_genetic_height_cm = estimated_genetic_height_cm + 5
#     unoptimized_estimated_genetic_height_cm = estimated_genetic_height_cm - 5

#     # If user already exceeded optimized ceiling
#     if current_cm_val > optimized_estimated_genetic_height_cm:
#         estimated_genetic_height_cm = current_cm_val
#         optimized_estimated_genetic_height_cm = current_cm_val + 5
#         unoptimized_estimated_genetic_height_cm = current_cm_val - 5

#     profile_fields = get_profile_fields(profile_dict, ["age", "gender"], default=None)
#     total_max_loss = sum(
#         segment["max_loss_cm"]
#         for segment in optimization_breakdown.values()
#     )
#     total_current_loss = sum(
#         segment["current_loss_cm"]
#         for segment in optimization_breakdown.values()
#     )

#     # ── Scan Limit Logic ──────────────────────────────
#     is_paid = subscription_data.get("is_paid", False)
#     last_scan = profile.last_scan
#     now = timezone.now()

#     can_scan = True
#     remaining_scans = "unlimited"
#     scan_message = "Unlimited scans available."

#     if not is_paid:
#         remaining_scans = 1
        
#         if last_scan and last_scan.year == now.year and last_scan.month == now.month:
#             can_scan = False
#             remaining_scans = 0
#             scan_message = "Free plan allows only 1 scan per month."
#         else:
#             can_scan = True
#             remaining_scans = 1
#             scan_message = "You can use your 1 free scan for this month."

#     return Response(
#         {
#             "message": "Posture Questions retrieved successfully",
#             "user": {
#                 "id": user.id,
#                 "username": user.username,
#                 "email": user.email,
#             },
#             "scan_access": {
#                 "can_scan": can_scan,
#                 "remaining_scans": remaining_scans,
#                 "scan_message": scan_message,
#             },
#             'subscription': subscription_data, 
#             "today_total_score": today_total_score,
#             "last_scan": profile_dict.get("last_scan"),
#             "scan_days": 30,
#             "profile": profile_fields,
#             "ai_analysis": ai_analysis,
#             "optimization_breakdown": optimization_breakdown,
#             "total_max_loss": total_max_loss,
#             "total_current_loss": total_current_loss,
#             "chart_breakdown": chart_breakdown,
#             "growth_projection": {
#                 "father_height_cm": float(profile_dict.get("father_height_cm", 0.0)),
#                 "mother_height_cm": float(profile_dict.get("mother_height_cm", 0.0)),
#                 "current_height_cm": current_cm_val,
#                 "optimized_estimated_genetic_height_cm": optimized_estimated_genetic_height_cm,
#                 "estimated_genetic_height_cm": estimated_genetic_height_cm,
#                 "unoptimized_estimated_genetic_height_cm": unoptimized_estimated_genetic_height_cm,
#                 "genetic_height_difference": genetic_diff,
#                 "genetic_status": genetic_status,
#                 "green_dots": green_dots,
#                 "growth_projections": projections,
#                 "score_summary": score_summary,
#                 "segment_gain_cm": segment_gains_today,
#             },
#             "streaks": streaks,
#             "max_height": 5.3,
#             "response_data": response_data
#         },
#         status=status.HTTP_200_OK,
#     )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_posture_questions(request):
    user = request.user
    rescan = request.query_params.get('rescan')

    # ── 1. Check subscription ──────────────────────────────
    subscription_status = check_subscription_or_response(user)

    if subscription_status.data.get("expired", True):
        return subscription_status

    # ── 2. Fetch profile ──────────────────────────────
    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        return Response({"error": "User profile not found."}, status=404)

    profile_dict = model_to_dict(profile)
    _ae_raw = get_user_age_exact(user)
    if _ae_raw is not None:
        age_exact = float(_ae_raw)
    else:
        try:
            age_exact = float(profile_dict.get("age") or 0.0)
        except (TypeError, ValueError):
            age_exact = 0.0
    age_years = int(age_exact) if age_exact >= 0 else 0
    # Decimal-age bands must match /dashboard-new (Section 16 / trial boundaries).
    is_teen_track = bool(13.0 <= age_exact <= 20.999)
    is_adult_track = bool(age_exact >= 21.0)
    transitioned_to_adult = False
    desired_tier = "adult" if age_exact >= 21.0 else "teen"
    update_user_fields = []
    if getattr(user, "account_tier", None) != desired_tier:
        user.account_tier = desired_tier
        update_user_fields.append("account_tier")
    if age_exact >= 21.0 and str(profile.age or "") != str(age_years):
        profile.age = str(age_years)
        profile.save(update_fields=["age"])
        profile_dict["age"] = profile.age
        transitioned_to_adult = True
        if getattr(user, "transitioned_to_adult_at", None) is None:
            user.transitioned_to_adult_at = timezone.now()
            update_user_fields.append("transitioned_to_adult_at")
    if update_user_fields:
        user.save(update_fields=update_user_fields)

    # ── 3. Latest posture report ─────────────────
    posture_report = PostureReport.objects.filter(user=user).order_by('-created_at').first()

    # ── 4. Genetic Height Estimate ─────────────────────
    genetic_estimate = GeneticHeightService.get_or_create_genetic_estimate(
        user, profile_dict
    )
    # ── 5. Growth projections ─────
    projections = GrowthProjectionService.get_projection_data(genetic_estimate)
    subscription_data = subscription_status.data

    score_summary = get_user_score_summary(user=user,subscription_data=subscription_data)
    today_total_score = get_user_score_summary(user=user,subscription_data=subscription_data, mode="today_total_score")

    # ── 6. Date handling ─────────────────────
    date_str = request.query_params.get("date")
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else None
    except ValueError:
        return Response({"error": "Invalid date format. Use YYYY-MM-DD."}, status=400)

    green_dots = calculate_green_dots(user=user, target_date=target_date)

    
    monetization = compute_monetization_flags(age_years, subscription_data, age_exact=age_exact)
    is_paid = monetization["is_paid"]
    streaks = get_user_streaks(user,subscription_data)
    # ── 8. Posture AI analysis ────────────────────────────

    
    ai_analysis, optimization_breakdown = PostureAnalysisService.get_posture_analysis(
        user=user,
        profile_dict=profile_dict,
        rescan=rescan
    )
    # Determine posture source for spec-aligned dashboard messaging.
    # Spec: scan completion is the primary indicator for scan-backed posture state.
    # If a scan timestamp exists but PostureReport row is absent, still treat as scan-backed.
    has_scan = bool(profile.last_scan) or bool(posture_report)
    posture_source = "ai_scan" if has_scan else "pending_scan"
    if posture_report is None and (is_adult_track or is_teen_track):
        posture_q = PostureQuestionService.get_posture_questions(user)
        # v3.3: questionnaire fallback is allowed for teens too.
        if posture_q and bool(get_user_runtime_state_snapshot(user).get("questionnaire_completed")):
            clamp_min = 1.0 if is_adult_track else 0.0
            manual = build_section3_manual_breakdown(posture_q, clamp_min_cm=clamp_min)
            optimization_breakdown = manual["optimization_breakdown"]
            posture_source = "manual_questionnaire"
            ai_analysis = {
                "summary": "Manual posture estimate from questionnaire",
                "note": "Section 3 weighted scoring applied.",
                "raw_score_cm": manual["raw_score_cm"],
                "total_recoverable_loss_cm": manual["total_recoverable_loss_cm"],
            }

    # ── 9. Ensure routine exists ───────────────────────────
    # v3.3: teen unlock can be scan OR questionnaire completion.
    runtime_state = get_user_runtime_state_snapshot(user)
    teen_unlocked = bool(runtime_state.get("scan_completed") or runtime_state.get("questionnaire_completed"))
    teen_scan_required = bool(is_teen_track and (not teen_unlocked))
    if not teen_scan_required:
        RoutineService.ensure_active_routine(user, optimization_breakdown)

     # ───────────────────────────────────────────────────────
    # ✅ CONVERT TO TEEN PROFILE (AI DOMAIN MODEL)
    # ───────────────────────────────────────────────────────
    teen_profile = map_userprofile_to_teenprofile(
        profile,
        optimization_breakdown,
        posture_report,
    )

    # ── 6. Optimized Height Calculation ────────────────────
    optimized_height_cm = None
    optimized_result = compute_optimized_height(teen_profile)

    # ── 7. Height calculations ─────────────────────
    current_cm_val = float(profile_dict.get("base_height_cm") or profile_dict.get("current_height_cm", 0.0))
    # Spec: separate *genetic target* from *true optimized* and from *current height*.
    genetic_height_cm = float(optimized_result.get("mph_height_cm") or 0.0)
    true_optimized_cm = float(optimized_result.get("optimized_height_cm") or 0.0)
    genetic_diff, genetic_status = GrowthProjectionService.calculate_genetic_status(
        current_cm_val, genetic_height_cm
    )
    
    if user.profile_step != "completed":
        user.profile_step = "completed"
        user.save(update_fields=["profile_step"])

    

    # Section 16 teen targets:
    # - genetic_blue target = MPH
    # - us_optimized_red target = MPH + posture potential (capped by premium posture boost max)
    # - true_optimized_green target = full optimized height (paid/trial reveal), never below red
    red_us_optimized_target_cm = float(genetic_height_cm + min(float(teen_profile.posture_potential_cm or 0.0), float(POSTURE_BOOST_MAX_CM)))
    if true_optimized_cm > 0:
        true_optimized_cm = max(true_optimized_cm, red_us_optimized_target_cm)
    # UI reveal: true optimized is only shown for paid teen (or trial access is handled by dashboard-new lock flag).
    optimized_height_cm = true_optimized_cm if (is_paid and is_teen_track) else None
        
   
    current_height_cm = teen_profile.current_height_cm
    # print('optimized_height_cm')
    # print(optimized_height_cm)
    # print('current_height_cm')
    # print(current_height_cm)
    # print('genetic_height_cm')
    # print(genetic_height_cm)
    # Base genetic estimate
    

    # Unoptimized is conservative (2cm below genetic) per spec fallback used elsewhere.
    lower_bound_cm = genetic_height_cm - 2
    optimized_ceiling_cm = red_us_optimized_target_cm

    chart_breakdown = calculate_height_projection(
        current_height_cm,
        optimized_ceiling_cm,
        genetic_height_cm,
        lower_bound_cm,
        teen_profile.sex,
    )


    # Pass TeenProfile to height engine
    

    # ── 12. Projection targets for Section 16 chart labels ─────────────────
    # These must not be arbitrary +/- 5cm offsets; they are the chart endpoints.
    optimized_estimated_genetic_height_cm = round(red_us_optimized_target_cm, 2)
    unoptimized_estimated_genetic_height_cm = round(genetic_height_cm - 2.0, 2)
    estimated_height_user = genetic_height_cm

    profile_fields = get_profile_fields(profile_dict, ["age", "gender", "g_p_height_change"], default=None)

    total_max_loss = sum(
        segment["max_loss_cm"]
        for segment in optimization_breakdown.values()
    )

    total_current_loss = sum(
        segment["current_loss_cm"]
        for segment in optimization_breakdown.values()
    )
    # runtime_state already computed above (includes questionnaire unlock state).
    runtime_total_recoverable_loss_cm = round(
        float(runtime_state.get("total_recoverable_loss_um", 0)) / 10000.0,
        4,
    )
    if runtime_total_recoverable_loss_cm > 0:
        total_max_loss = runtime_total_recoverable_loss_cm

    # ── 13. Scan Limit Logic ──────────────────────────────
    last_scan = profile.last_scan
    now = timezone.now()
    days_since_scan = (now - last_scan).days if last_scan else None
    rescan_days = 7
    initial_scan_available = bool(days_since_scan is None)
    can_scan = bool(
        initial_scan_available
        or (is_paid and days_since_scan is not None and days_since_scan >= rescan_days)
    )
    remaining_scans = "unlimited" if is_paid else 0
    if days_since_scan is None:
        questionnaire_done = bool(runtime_state.get("questionnaire_completed"))
        if is_adult_track and questionnaire_done:
            scan_message = "Manual posture assessment completed. Scan is optional."
        elif is_teen_track and questionnaire_done:
            # v3.3: teen questionnaire unlocks without scan.
            scan_message = "Manual posture assessment completed."
        else:
            scan_message = "Initial scan required."
    else:
        days_left = max(0, rescan_days - days_since_scan)
        if is_adult_track and not is_paid:
            # Free adult state is always locked/read-only for re-scan timer text.
            scan_message = f"Re-scan in {days_left} days."
        else:
            scan_message = f"Re-scan in {days_left} days." if days_left > 0 else "Re-scan available."
    # v3.3: teen unlock can be scan OR questionnaire completion (do not rely on last_scan).
    teen_scan_required = bool(is_teen_track and (not teen_unlocked))
    max_height_cm = None

    age = age_years

    if is_teen_track:
        response_data = get_height_view(
            user=user,
            profile=teen_profile,   # ✅ ALWAYS TeenProfile
            is_paid=is_paid,
            optimized_height_cm=optimized_height_cm,
            total_score=score_summary.get("total_engine1_points", 0),
        )
        if is_paid:
            optimized_result = compute_optimized_height(teen_profile)
            max_height_cm = optimized_result["optimized_height_cm"]
        else:
            max_height_cm = genetic_estimate.estimated_height_cm

    elif is_adult_track:
        response_data = get_height_view(
            user=user,
            profile=teen_profile,   # ✅ ALWAYS TeenProfile
            is_paid=is_paid,
            optimized_height_cm=total_current_loss,
            total_score=score_summary.get("total_engine1_points", 0),
        )
        if is_paid:
            max_height_cm = (
                teen_profile.current_height_cm +
                teen_profile.posture_potential_cm
            )
        else:
            max_height_cm = teen_profile.current_height_cm

    # Build canonical diagnostics first and use it as single display source.
    posture_optimization_diagnostics = build_posture_optimization_diagnostics(
        user=user,
        optimization_breakdown=optimization_breakdown,
        source=posture_source,
        rescan_days=rescan_days,
    )
    canonical_scan_completed = bool(runtime_state.get("scan_completed") or bool(last_scan))
    canonical_total_recoverable_cm = float(
        posture_optimization_diagnostics.get("total_recoverable_loss_cm", 0.0) or 0.0
    )
    # Spec naming convention aliases (UI labels vs backend keys).
    # Use runtime ledger first (authoritative); fallback to score-derived conversion.
    runtime_height_um = runtime_state.get("current_height_um")
    posture_plus_cumulative_cm = round(float(score_summary.get("total_engine1_points", 0)) * 0.001, 4)
    if is_adult_track and runtime_height_um is not None:
        posture_plus_cumulative_cm = round(float(runtime_height_um) / 10000.0, 4)
    if is_adult_track:
        # Section 4.1: Recovered So Far tracks validated posture gains.
        validated_dates = list(
            DailyLog.objects.filter(user=user, validated=True).values_list("log_date", flat=True)
        )
        validated_engine1_um = 0
        if validated_dates:
            q = HeightLedger.objects.filter(
                user=user,
                entry_type="daily_compute",
                log_date__in=validated_dates,
            )
            validated_engine1_um = int(q.aggregate(v=Sum("engine1_delta_um")).get("v") or 0)
            # Backward compatibility: fall back to metadata if older rows weren't backfilled yet.
            if validated_engine1_um == 0 and q.exists():
                for row in q.only("metadata").iterator(chunk_size=500):
                    try:
                        validated_engine1_um += int((row.metadata or {}).get("engine1_delta_um", 0) or 0)
                    except Exception:
                        logger.exception(
                            "Failed reading engine1_delta_um from HeightLedger.metadata",
                            extra={"row_id": getattr(row, "id", None)},
                        )
                        continue
        posture_plus_cumulative_cm = round(validated_engine1_um / 10000.0, 4)
    genetic_plus_cumulative_cm = round(
        float(score_summary.get("teen_engine2_boost_cm", 0)),
        4,
    ) if is_teen_track else 0.0
    teen_engine1_cumulative_cm = 0.0
    teen_engine2_cumulative_cm = 0.0
    teen_bio_cumulative_cm = 0.0
    teen_engine1_today_cm = 0.0
    teen_engine2_today_cm = 0.0
    teen_bio_today_cm = 0.0
    # Trial-end snapshot cumulatives (used for post-day-7 unpaid flatline behavior).
    teen_engine1_cumulative_trial_cm = 0.0
    teen_engine2_cumulative_trial_cm = 0.0
    teen_bio_cumulative_trial_cm = 0.0
    trial_cutoff_date = None
    try:
        _ts = getattr(user, "trial_start", None)
        if _ts:
            # Spec (Sections 5.5 / 13.3): trial day boundaries are based on the user's local day.
            # Use the user's local date of trial_start as day 1.
            trial_start_local_date = user_localize_dt(user, _ts).date()
            # Last full trial day (day 1..7 inclusive) is local start date + 6 days.
            trial_cutoff_date = trial_start_local_date + timedelta(days=6)
    except Exception:
        trial_cutoff_date = None
    user_local_today = user_today(user)
    if is_teen_track:
        qs = HeightLedger.objects.filter(user=user, entry_type="daily_compute")

        agg_all = qs.aggregate(
            e1_um=Sum("engine1_delta_um"),
            bio_um=Sum("bio_delta_um"),
            e2_dm=Sum("engine2_delta_dm"),
        )
        teen_engine1_cumulative_cm = float(int(agg_all.get("e1_um") or 0) / 10000.0)
        teen_engine2_cumulative_cm = float(int(agg_all.get("e2_dm") or 0) / 100000.0)
        teen_bio_cumulative_cm = float(int(agg_all.get("bio_um") or 0) / 10000.0)

        if trial_cutoff_date is not None:
            agg_trial = qs.filter(log_date__lte=trial_cutoff_date).aggregate(
                e1_um=Sum("engine1_delta_um"),
                bio_um=Sum("bio_delta_um"),
                e2_dm=Sum("engine2_delta_dm"),
            )
            teen_engine1_cumulative_trial_cm = float(int(agg_trial.get("e1_um") or 0) / 10000.0)
            teen_engine2_cumulative_trial_cm = float(int(agg_trial.get("e2_dm") or 0) / 100000.0)
            teen_bio_cumulative_trial_cm = float(int(agg_trial.get("bio_um") or 0) / 10000.0)

        agg_today = qs.filter(log_date=user_local_today).aggregate(
            e1_um=Sum("engine1_delta_um"),
            bio_um=Sum("bio_delta_um"),
            e2_dm=Sum("engine2_delta_dm"),
        )
        teen_engine1_today_cm = float(int(agg_today.get("e1_um") or 0) / 10000.0)
        teen_engine2_today_cm = float(int(agg_today.get("e2_dm") or 0) / 100000.0)
        teen_bio_today_cm = float(int(agg_today.get("bio_um") or 0) / 10000.0)

        # Backward compatibility: if we have rows but totals are zeros, recompute from metadata.
        if (
            teen_engine1_cumulative_cm == 0.0
            and teen_engine2_cumulative_cm == 0.0
            and teen_bio_cumulative_cm == 0.0
            and qs.exists()
        ):
            teen_engine1_cumulative_cm = 0.0
            teen_engine2_cumulative_cm = 0.0
            teen_bio_cumulative_cm = 0.0
            teen_engine1_cumulative_trial_cm = 0.0
            teen_engine2_cumulative_trial_cm = 0.0
            teen_bio_cumulative_trial_cm = 0.0
            teen_engine1_today_cm = 0.0
            teen_engine2_today_cm = 0.0
            teen_bio_today_cm = 0.0
            for row in qs.only("metadata", "log_date", "engine2_delta_dm").iterator(chunk_size=500):
                try:
                    md = row.metadata or {}
                    e1_um = int(md.get("engine1_delta_um", 0) or 0)
                    bio_um = int(md.get("bio_delta_um", 0) or 0)
                    e2_dm = int(getattr(row, "engine2_delta_dm", 0) or 0) or int(md.get("engine2_delta_dm", 0) or 0)
                    teen_engine1_cumulative_cm += (e1_um / 10000.0)
                    teen_engine2_cumulative_cm += (float(e2_dm) / 100000.0)
                    teen_bio_cumulative_cm += (bio_um / 10000.0)
                    if trial_cutoff_date is not None and row.log_date <= trial_cutoff_date:
                        teen_engine1_cumulative_trial_cm += (e1_um / 10000.0)
                        teen_engine2_cumulative_trial_cm += (float(e2_dm) / 100000.0)
                        teen_bio_cumulative_trial_cm += (bio_um / 10000.0)
                    if row.log_date == user_local_today:
                        teen_engine1_today_cm += (e1_um / 10000.0)
                        teen_engine2_today_cm += (float(e2_dm) / 100000.0)
                        teen_bio_today_cm += (bio_um / 10000.0)
                except Exception:
                    continue
        teen_engine1_cumulative_cm = round(teen_engine1_cumulative_cm, 4)
        teen_engine2_cumulative_cm = round(teen_engine2_cumulative_cm, 4)
        teen_bio_cumulative_cm = round(teen_bio_cumulative_cm, 4)
        teen_engine1_cumulative_trial_cm = round(teen_engine1_cumulative_trial_cm, 4)
        teen_engine2_cumulative_trial_cm = round(teen_engine2_cumulative_trial_cm, 4)
        teen_bio_cumulative_trial_cm = round(teen_bio_cumulative_trial_cm, 4)
        teen_engine1_today_cm = round(teen_engine1_today_cm, 4)
        teen_engine2_today_cm = round(teen_engine2_today_cm, 4)
        teen_bio_today_cm = round(teen_bio_today_cm, 4)
    # Daily Gains means "today" gain, not cumulative.
    daily_gains_cm = 0.0
    optimized_height_for_ui = (
        optimized_result.get("optimized_height_cm")
        if is_paid and is_teen_track
        else None
    )
    posture_plus_daily_gain_cm = 0.0
    if is_teen_track:
        posture_plus_daily_gain_cm = round(
            float(score_summary.get("today", {}).get("workout_score", 0) or 0) * 0.001,
            4,
        )
    current_loss_segments = {
        "spinal_compression": round(float(posture_optimization_diagnostics.get("segments", {}).get("spinal_compression", {}).get("current_loss_cm", 0.0) or 0.0), 4),
        "posture_collapse": round(float(posture_optimization_diagnostics.get("segments", {}).get("posture_collapse", {}).get("current_loss_cm", 0.0) or 0.0), 4),
        "pelvic_tilt_back": round(float(posture_optimization_diagnostics.get("segments", {}).get("pelvic_tilt_back", {}).get("current_loss_cm", 0.0) or 0.0), 4),
        "leg_hamstring": round(float(posture_optimization_diagnostics.get("segments", {}).get("leg_hamstring", {}).get("current_loss_cm", 0.0) or 0.0), 4),
    }
    rescan_timer_days = None if days_since_scan is None else max(0, rescan_days - days_since_scan)
    today_block = score_summary.get("today", {}) if isinstance(score_summary, dict) else {}
    today_workout_points = float(today_block.get("workout_score", 0) or 0)
    today_food_points = float(today_block.get("food_score", 0) or 0)
    adult_daily_gains_cm = round((today_workout_points + min(today_food_points, 12.0)) * 0.001, 4)
    if not monetization["conversion_enabled"]:
        adult_daily_gains_cm = 0.0
    teen_daily_posture_plus_cm = round(today_workout_points * 0.001, 4)
    if is_adult_track:
        posture_plus_daily_gain_cm = adult_daily_gains_cm
    if is_adult_track:
        daily_gains_cm = adult_daily_gains_cm
    else:
        # Section 5.3: Daily Gains = Genetic+ (bio+engine2 today) + Posture+ today
        daily_gains_cm = round(teen_engine1_today_cm + teen_engine2_today_cm + teen_bio_today_cm, 4)
    adult_nutrition_pct = None
    if is_adult_track:
        today_entries = NutraEntry.objects.filter(
            session__user=user,
            session__date=user_local_today,
            food__isnull=False,
        ).select_related("module")
        disc_count = 0
        muscle_count = 0
        for entry in today_entries:
            module = getattr(entry, "module", None)
            module_name = str(getattr(module, "name", "") or "").lower()
            module_cat = str(getattr(module, "nutrition_category", "") or "").lower()
            if (module_cat == "disc" or any(k in module_name for k in ("disc", "lubrication", "spine"))) and disc_count < 2:
                disc_count += 1
            elif (module_cat == "muscle" or any(k in module_name for k in ("muscle", "repair", "fuel"))) and muscle_count < 2:
                muscle_count += 1
        adult_nutrition_pct = int(max(0, min(100, (disc_count + muscle_count) * 25)))
    teen_food_points_today = float(today_food_points)
    teen_nutrition_dots = (
        teen_nutrition_dots_from_food_points(teen_food_points_today) if is_teen_track else 0
    )
    teen_lifestyle_dots = teen_lifestyle_dots_for_day(user, user_local_today) if is_teen_track else 0
    progress_bars = {}
    for seg, seg_data in posture_optimization_diagnostics.get("segments", {}).items():
        max_loss = float(seg_data.get("max_loss_cm", 0) or 0)
        cur_loss = float(seg_data.get("current_loss_cm", 0) or 0)
        pct = 100 if max_loss <= 0 else int(round((1 - (cur_loss / max_loss)) * 100))
        progress_bars[seg] = max(0, min(100, pct))
    trial_day_int = monetization["trial_day"]
    full_access_trial_active = bool(monetization["is_teen"] and monetization["is_trial"] and not monetization["full_access_trial_expired"])
    full_access_trial_expired = monetization["full_access_trial_expired"]
    # Spec (Section 5.6 / 7.2): True Optimized Height is NEVER revealed until payment,
    # including during the 7-day teen trial.
    can_view_true_optimized = bool(is_teen_track and is_paid)

    today_local = user_local_today
    assigned_posture_qs = UserRoutineExercise.objects.filter(
        routine__user=user,
        routine__is_active=True,
        routine__routine_type=RoutineType.POSTURE,
    )
    assigned_core_count = assigned_posture_qs.filter(tier=Tier.CORE).count()
    assigned_rec_count = assigned_posture_qs.filter(tier=Tier.RECOMMENDED).count()
    assigned_beast_count = assigned_posture_qs.filter(tier=Tier.BEAST).count()
    assigned_posture_total = assigned_posture_qs.count()
    completed_posture_qs_all = WorkoutEntry.objects.filter(
        session__user=user,
        session__date=today_local,
        session__user_routine__routine_type=RoutineType.POSTURE,
    )
    # Primary path (preferred): count distinct assigned routine exercises via FK.
    completed_posture_qs = completed_posture_qs_all.filter(user_routine_exercise__isnull=False)
    completed_posture_total_fk = completed_posture_qs.values("user_routine_exercise_id").distinct().count()
    completed_core_count_fk = completed_posture_qs.filter(user_routine_exercise__tier=Tier.CORE).values(
        "user_routine_exercise_id"
    ).distinct().count()

    # Fallback path: older rows may have user_routine_exercise=NULL; count by exercise_id intersect.
    assigned_exercise_ids = set(assigned_posture_qs.values_list("exercise_id", flat=True))
    completed_exercise_ids = set(completed_posture_qs_all.values_list("exercise_id", flat=True).distinct())
    completed_posture_total_ex = len(assigned_exercise_ids.intersection(completed_exercise_ids))
    completed_core_exercise_ids = set(
        assigned_posture_qs.filter(tier=Tier.CORE).values_list("exercise_id", flat=True)
    )
    completed_core_count_ex = len(completed_core_exercise_ids.intersection(completed_exercise_ids))

    completed_posture_total = max(completed_posture_total_fk, completed_posture_total_ex)
    completed_core_count = max(completed_core_count_fk, completed_core_count_ex)

    # Teen dashboard progress includes HGH routine as well (POSTURE + HGH combined).
    assigned_hgh_total = 0
    completed_hgh_total = 0
    if is_teen_track:
        assigned_hgh_qs = UserRoutineExercise.objects.filter(
            routine__user=user,
            routine__is_active=True,
            routine__routine_type=RoutineType.HGH,
        )
        assigned_hgh_total = assigned_hgh_qs.count()

        completed_hgh_qs_all = WorkoutEntry.objects.filter(
            session__user=user,
            session__date=today_local,
            session__user_routine__routine_type=RoutineType.HGH,
        )
        completed_hgh_qs = completed_hgh_qs_all.filter(user_routine_exercise__isnull=False)
        completed_hgh_total_fk = completed_hgh_qs.values("user_routine_exercise_id").distinct().count()

        assigned_hgh_exercise_ids = set(assigned_hgh_qs.values_list("exercise_id", flat=True))
        completed_hgh_exercise_ids = set(completed_hgh_qs_all.values_list("exercise_id", flat=True).distinct())
        completed_hgh_total_ex = len(assigned_hgh_exercise_ids.intersection(completed_hgh_exercise_ids))

        completed_hgh_total = max(completed_hgh_total_fk, completed_hgh_total_ex)

    # Spec lock: if teen initial scan is required, force fully locked posture state.
    if teen_scan_required:
        # In scan-required locked state, routine progress should not reflect any
        # previously assigned routines. Treat today's assigned/completed as zero.
        assigned_core_count = 0
        assigned_rec_count = 0
        assigned_beast_count = 0
        assigned_posture_total = 0
        completed_posture_total = 0
        completed_core_count = 0
        assigned_hgh_total = 0
        completed_hgh_total = 0

        posture_source = "pending_scan"
        ai_analysis = {
            "summary": "Initial scan required before posture analysis is available.",
            "status": "pending_scan",
            "recommendations": [],
        }
        chart_breakdown = None
        projections = None
        optimized_result = {
            "current_height_cm": current_cm_val,
            "posture_gain_cm": 0.0,
            "bio_age_modifier_cm": 0.0,
            "frame_modifier_cm": 0.0,
            "wingspan_modifier_cm": 0.0,
            "puberty_score": 0,
            "mph_height_cm": genetic_height_cm,
            "optimized_height_cm": None,
        }
        optimization_breakdown = default_optimization_breakdown_pending_scan()
        posture_optimization_diagnostics = {
            "scan_completed": False,
            "source": "pending_scan",
            "total_recoverable_loss_cm": 0.0,
            "total_current_loss_cm": 0.0,
            "segments": optimization_breakdown,
            "re_scan_timer_days": None,
            "last_scan_at": None,
            "next_scan_at": None,
        }
        total_current_loss = 0.0
        total_max_loss = 0.0
        current_loss_segments = {
            "spinal_compression": 0.0,
            "posture_collapse": 0.0,
            "pelvic_tilt_back": 0.0,
            "leg_hamstring": 0.0,
        }
        progress_bars = {
            "spinal_compression": 0,
            "posture_collapse": 0,
            "pelvic_tilt_back": 0,
            "leg_hamstring": 0,
        }
        posture_plus_daily_gain_cm = 0.0
        posture_plus_cumulative_cm = 0.0
        genetic_plus_cumulative_cm = 0.0
        daily_gains_cm = 0.0
        teen_daily_posture_plus_cm = 0.0
        adult_daily_gains_cm = 0.0
        teen_nutrition_dots = 0
        teen_lifestyle_dots = 0
        canonical_total_recoverable_cm = 0.0
        canonical_scan_completed = False
        optimized_height_for_ui = None
    elif can_view_true_optimized:
        optimized_height_for_ui = optimized_result.get("optimized_height_cm")
    else:
        optimized_height_for_ui = None

    # ── 14. FINAL RESPONSE ──────────────────────────────
    return Response(
        {
            "message": "Posture Questions retrieved successfully",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            },
            "scan_access": {
                "can_scan": can_scan,
                "remaining_scans": remaining_scans,
                "scan_message": scan_message,
                "rescan_days": rescan_days,
                "days_since_scan": days_since_scan,
                "teen_scan_required": teen_scan_required,
                "scan_completed": canonical_scan_completed,
                "Re_Scan_Timer": rescan_timer_days,
            },
            "subscription": subscription_data,
            "today_total_score": today_total_score,
            "last_scan": profile_dict.get("last_scan"),
            "profile": profile_fields,
            "ai_analysis": ai_analysis,
            "optimization_breakdown": optimization_breakdown,
            "chart_breakdown": chart_breakdown,
            "total_max_loss": total_max_loss,
            "total_current_loss": total_current_loss,
            "runtime_state": runtime_state,
            "posture_optimization_diagnostics": posture_optimization_diagnostics,
            "section8_mapping_summary": {
                "table_version": "8.x",
                "section1_reference": {
                    "segment_structural_ceiling_cm": TOTAL_STRUCTURAL_CEILING_CM,
                    "teen_postureplus_lifetime_cap_cm": OPTIMIZATION_GAP_CM,
                    "premium_posture_boost_cap_cm": POSTURE_BOOST_MAX_CM,
                    "points_to_cm_engine1": POINTS_TO_CM_ENGINE1,
                    "points_to_cm_engine2": POINTS_TO_CM_ENGINE2,
                    "ui_to_code_variable_names": UI_TO_CODE_VARIABLE_NAMES,
                },
                "adult_dashboard_mapping": {
                    "daily_gains_formula": "(posture_pts + min(nutrition_pts,12)) * 0.001",
                    "daily_gains_cm": adult_daily_gains_cm,
                    "top_graph_height_formula": "Base_Height + SUM(Daily_Gains)",
                    "target_height_formula": "Base_Height + Total_Recoverable_Loss",
                    "rescan_timer_formula": "7 - elapsed_days_since_last_scan",
                    "rescan_timer_days": rescan_timer_days,
                    "progress_bars_formula": "if Max_Loss<=0 then 100 else (1-Current_Loss/Max_Loss)*100",
                    "progress_bars_percent": progress_bars,
                    "adult_nutrition_percent_formula": "(foods_logged / 4) * 100",
                    "adult_nutrition_percent": adult_nutrition_pct,
                },
                "teen_dashboard_mapping": {
                    "genetic_plus_source": "Daily_Bio_Gain interpolation table (premium path)",
                    "posture_plus_formula": "posture_exercise_points * 0.001",
                    "posture_plus_daily_cm": teen_engine1_today_cm,
                    "daily_gains_formula": "Genetic+ + Posture+",
                    "daily_gains_cm": daily_gains_cm,
                    "height_formula": "Base_Height + Genetic_Cumulative + PosturePlus_Cumulative",
                    "posture_lifetime_cap_cm": OPTIMIZATION_GAP_CM,
                    "progress_ratio_segments": "30/35/25/10",
                    "progress_bars_percent": progress_bars,
                    "teen_nutrition_dots_formula": "1-10=1, 11-20=2, 21-30=3, 31+=4",
                    "teen_nutrition_dots": teen_nutrition_dots,
                    "teen_lifestyle_dots": teen_lifestyle_dots,
                    "teen_lifestyle_dots_formula": "sleep>=5, sun>=6 (10–20min tier), med>=1, hydration>=1",
                    "teen_lifestyle_nutrition_combined_percent": (
                        min(100, int(round((teen_nutrition_dots + teen_lifestyle_dots) * 12.5)))
                        if is_teen_track
                        else None
                    ),
                },
            },
            "section9_quick_reference": {
                "point_to_height_engine1_cm_per_point": 0.001,
                "point_to_height_engine2_cm_per_point": 0.00005,
                "adult_daily_gain_formula": "(posture_pts + min(nutrition_pts,12)) * 0.001",
                "teen_postureplus_daily_formula": "posture_pts * 0.001",
                "teen_engine2_caps": {
                    "nutrition": 35,
                    "sleep": 10,
                    "sunlight": 6,
                    "meditation": 2,
                    "hydration": 1,
                    "hgh_total": 30,
                    "hgh_per_exercise_max_completions": 2,
                },
                "posture_segment_max_loss_cm": {
                    "spinal_compression": 3.0,
                    "posture_collapse": 2.5,
                    "pelvic_tilt_back": 1.5,
                    "leg_hamstring": 1.0,
                },
                "streak_rule_adult": "All Core 6 + min1 food in Disc and Muscle categories by 23:59 local.",
                "streak_rule_teen": "All core posture + core HGH + min1 food by 23:59 local.",
                "leaderboard_tier_split": "Adults and teens are ranked separately.",
                "rescan_cadence_days": 7,
                "teen_trial_days": 7,
                "food_validation_window": "00:00-23:59 local; no cross-midnight carry.",
            },
            "section10_assignment_contract": {
                "segment_scoring_source": "questionnaire_then_fallback_optimization_breakdown",
                "tie_break_priority": ["spinal_compression", "posture_collapse", "pelvic_tilt_back", "leg_hamstring"],
                "adult_assignment": "core6 + 2 recommended + 2 beast",
                "teen_assignment_13_17": "core4 + 1 recommended + 1 beast (posture)",
                "teen_assignment_18_20": "core6 + 2 recommended + 2 beast (posture)",
                "hgh_assignment": "core2 + 1 beast by ranked segment fallback",
            },
            "section4_contract": {
                "scan_completed": canonical_scan_completed,
                "base_height_cm": round(current_cm_val, 4),
                "recovered_so_far_cm": posture_plus_cumulative_cm,
                "daily_gains_cm": adult_daily_gains_cm if is_adult_track else posture_plus_daily_gain_cm,
                "height_live_cm": round(current_cm_val + posture_plus_cumulative_cm, 4) if is_adult_track else None,
                "total_recoverable_loss_cm": round(canonical_total_recoverable_cm, 4),
                "target_height_cm": round(current_cm_val + canonical_total_recoverable_cm, 4),
                "target_height_formula": "Base_Height + Total_Recoverable_Loss",
                "current_loss_cm": current_loss_segments,
                "postureplus_daily_gain_cm": posture_plus_daily_gain_cm,
                "postureplus_cumulative_cm": posture_plus_cumulative_cm,
                "rescan_timer_days": rescan_timer_days,
                # Exact-style aliases for strict spec consumers.
                "Scan_Completed": canonical_scan_completed,
                "Total_Recoverable_Loss_cm": round(canonical_total_recoverable_cm, 4),
                "Current_Loss_cm": current_loss_segments,
                "PosturePlus_Daily_Gain_cm": posture_plus_daily_gain_cm,
                "PosturePlus_Cumulative_cm": posture_plus_cumulative_cm,
                "Re_Scan_Timer": rescan_timer_days,
                "Base_Height_cm": round(current_cm_val, 4),
                "Recovered_So_Far_cm": posture_plus_cumulative_cm,
                "Daily_Gains_cm": adult_daily_gains_cm if is_adult_track else posture_plus_daily_gain_cm,
                "Height_Live_cm": round(current_cm_val + posture_plus_cumulative_cm, 4) if is_adult_track else None,
                "posture_exercises": {
                    # Teen UX: dashboard routine progress is POSTURE + HGH combined.
                    # Adult UX: posture routine only.
                    "assigned_total": (
                        (assigned_posture_total + assigned_hgh_total) if is_teen_track else assigned_posture_total
                    ),
                    "completed_total_today": (
                        (completed_posture_total + completed_hgh_total) if is_teen_track else completed_posture_total
                    ),
                    "exercises_done": (
                        (completed_posture_total + completed_hgh_total) if is_teen_track else completed_posture_total
                    ),
                    "total_exercises": (
                        (assigned_posture_total + assigned_hgh_total) if is_teen_track else assigned_posture_total
                    ),
                    "habits_logged": (
                        int(min(8, teen_nutrition_dots + teen_lifestyle_dots))
                        if is_teen_track
                        else int(max(0, min(4, (adult_nutrition_pct or 0) // 25)))
                    ),
                    "fraction_today": (
                        f"{(completed_posture_total + completed_hgh_total)}/{(assigned_posture_total + assigned_hgh_total) or 0}"
                        if is_teen_track
                        else f"{completed_posture_total}/{assigned_posture_total or 0}"
                    ),
                    "assigned_core": assigned_core_count,
                    "assigned_recommended": assigned_rec_count,
                    "assigned_beast_mode": assigned_beast_count,
                    "completed_core_today": completed_core_count,
                },
                "posture_nutrition_percent": adult_nutrition_pct if is_adult_track else None,
                "rescan_paywall_locked": bool(is_adult_track and not is_paid),
            },
            "total_max_height": (
                None if teen_scan_required else round(teen_profile.current_height_cm + teen_profile.posture_potential_cm, 1)
            ),
            "max_height": (
                None if teen_scan_required else round(teen_profile.posture_potential_cm, 1)
            ),
            "growth_projection": {
                "father_height_cm": float(profile_dict.get("father_height_cm") or 0.0),
                "mother_height_cm": float(profile_dict.get("mother_height_cm") or 0.0),
                "current_height_cm": current_cm_val,
                "optimized_estimated_genetic_height_cm": (
                    None if teen_scan_required else optimized_estimated_genetic_height_cm
                ),
                "estimated_genetic_height_cm": estimated_height_user,
                "unoptimized_estimated_genetic_height_cm": (
                    None if teen_scan_required else unoptimized_estimated_genetic_height_cm
                ),
                "genetic_height_difference": genetic_diff,
                "genetic_status": genetic_status,
                "green_dots": green_dots,
                "growth_projections": projections,
                "score_summary": score_summary,
                "engine1_total_points": score_summary.get("total_engine1_points", 0),
                "engine2_total_points": score_summary.get("total_engine2_points", 0),
                "teen_engine2_boost_cm": score_summary.get("teen_engine2_boost_cm", 0),
                "conversion_enabled": monetization["conversion_enabled"],
            },
            "section5_contract": {
                "genetic_average_cm": (
                    round(float(compute_genetic_average_cm(user, user_local_today)), 4)
                    if is_teen_track
                    else None
                ),
                "daily_genetic_average_gain_cm": (
                    round(float(compute_daily_genetic_average_gain_cm(user, user_local_today)), 6)
                    if is_teen_track
                    else None
                ),
                "genetic_plus_today_cm": round(teen_engine2_today_cm + teen_bio_today_cm, 4) if is_teen_track else 0.0,
                "posture_plus_today_cm": teen_engine1_today_cm if is_teen_track else 0.0,
                "daily_gains_today_cm": daily_gains_cm if is_teen_track else 0.0,
                "genetic_cumulative_cm": round(teen_engine2_cumulative_cm + teen_bio_cumulative_cm, 4) if is_teen_track else 0.0,
                "postureplus_cumulative_cm": teen_engine1_cumulative_cm if is_teen_track else 0.0,
                "postureplus_lifetime_cap_cm": OPTIMIZATION_GAP_CM if is_teen_track else None,
                "trial_day": trial_day_int if is_teen_track else None,
                "trial_active_day_1_7": full_access_trial_active if is_teen_track else False,
                "trial_expired_unpaid": full_access_trial_expired if is_teen_track else False,
                "display_lines": {
                    "blue_genetic_line_cm": (
                        round(current_cm_val + teen_engine2_cumulative_cm + teen_bio_cumulative_cm, 4)
                        if is_teen_track else None
                    ),
                    "red_us_optimized_line_cm": (
                        # Spec (Sections 5.5 / 7.2 / 11.5): after day 7 (unpaid), the red line flatlines
                        # while blue continues rising from biological growth.
                        round(
                            current_cm_val
                            + (
                                (teen_engine2_cumulative_trial_cm + teen_bio_cumulative_trial_cm)
                                if full_access_trial_expired
                                else (teen_engine2_cumulative_cm + teen_bio_cumulative_cm)
                            )
                            + (teen_engine1_cumulative_trial_cm if full_access_trial_expired else teen_engine1_cumulative_cm),
                            4,
                        )
                        if is_teen_track else None
                    ),
                    "green_true_optimized_cm": optimized_height_for_ui if is_teen_track else None,
                    "green_true_optimized_locked": bool(is_teen_track and not can_view_true_optimized),
                },
            },
            "section7_contract": {
                "adult": {
                    "free": {
                        "initial_scan_allowed": True,
                        "rescans_locked": True,
                        "workout_plan_locked": True,
                        "daily_tracking_locked": True,
                        "nutrition_lifestyle_locked": True,
                        "paywall_message": "Unlock your full recovery plan.",
                    },
                    "paid": {
                        "rescans_enabled": True,
                        "rescan_cadence_days": 7,
                        "workout_plan_enabled": True,
                        "daily_tracking_enabled": True,
                        "nutrition_lifestyle_enabled": True,
                    },
                },
                "teen": {
                    "day_1_7_full_access": bool(is_teen_track and full_access_trial_active),
                    "post_day_7_unpaid_locked": bool(is_teen_track and full_access_trial_expired),
                    "post_day_7_lock_message": (
                        "Unlock full Posture+, ultra-accurate True Optimized Height, and unlimited re-scans."
                        if is_teen_track and full_access_trial_expired else None
                    ),
                },
            },
            "streaks": streaks,
            "response_data": response_data,
            "section16_navigation": {
                "main_stack": "authenticated",
                "dashboard_variant": "teen" if is_teen_track else "adult",
                "current_screen_state": (
                    "dashboard_teen_locked_scan_required"
                    if is_teen_track and teen_scan_required
                    else ("dashboard_teen_active" if is_teen_track else "dashboard_adult_active")
                ),
                "primary_cta": (
                    "Scan First"
                    if is_teen_track and teen_scan_required
                    else "Start Today's Routine"
                ),
                "bottom_tabs": [
                    "dashboard",
                    "routine",
                    "nutrition",
                    "leaderboard",
                    "profile",
                ],
                "modals": {
                    "show_scan_modal": bool(initial_scan_available and can_scan),
                    "show_rescan_modal": bool((not teen_scan_required) and can_scan and days_since_scan is not None),
                    "show_paywall_modal": bool(full_access_trial_expired or (is_adult_track and not is_paid and not can_scan)),
                    "show_true_optimized_modal": bool(is_teen_track and can_view_true_optimized),
                    "show_age_transition_modal": bool(transitioned_to_adult),
                },
                "teen_unpaid_post_day7_banner": (
                    "Your body is still growing. Unlock GrowthMax+ to close the gap."
                    if is_teen_track and full_access_trial_expired
                    else None
                ),
                "scan_screen": {
                    "allow_skip": bool(is_adult_track),
                    "teen_skip_allowed": False,
                },
            },
            "optimized_result":optimized_result,
            "age_exact": round(age_exact, 3),
            "transitioned_to_adult": transitioned_to_adult,
            "trial_day": subscription_data.get("trial_day"),
            "full_access_trial_active": full_access_trial_active,
            "full_access_trial_day": trial_day_int,
            "full_access_trial_expired": full_access_trial_expired,
            "account_tier": getattr(user, "account_tier", None),
            "posture_source": posture_source,
            "ui_code_naming": {
                "posture_plus": {
                    "ui_label": "Posture+",
                    "code_variable": "PosturePlus",
                    "value_cm": posture_plus_cumulative_cm,
                },
                "genetic_plus": {
                    "ui_label": "Genetic+",
                    "code_variable": "Genetic_Daily_Gain",
                    "value_cm": genetic_plus_cumulative_cm,
                },
                "growth_max_plus": {
                    "ui_label": "Posture+",
                    "code_variable": "PosturePlus",
                    "value_cm": posture_plus_cumulative_cm,
                },
                "daily_gains": {
                    "ui_label": "Daily Gains",
                    "code_variable": "Daily_Gains",
                    "value_cm": daily_gains_cm,
                },
                "total_recovered": {
                    "ui_label": "Total Recovered",
                    "code_variable": "SUM(Daily_Gains)",
                    "value_cm": posture_plus_cumulative_cm,
                },
                "optimization_gap": {
                    "ui_label": "Optimization_Gap",
                    "code_variable": "Optimization_Gap",
                    "value_cm": 5.5 if is_teen_track else None,
                },
                "true_optimized_height": {
                    "ui_label": "True Optimized Height",
                    "code_variable": "Optimized_Height",
                    "value_cm": optimized_height_for_ui,
                },
            },
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_dashboard_new(request):
    """
    Unified dashboard contract for both teen and adult clients.
    Reuses canonical /dashboard computation, then maps to screen-focused payload.
    """
    user = request.user
    # `get_posture_questions` is wrapped by @api_view and expects a Django HttpRequest.
    # Inside DRF APIView, `request` is a DRF Request; use its underlying HttpRequest.
    http_request = getattr(request, "_request", request)
    base_response = get_posture_questions(http_request)
    if int(getattr(base_response, "status_code", 500)) != 200:
        return base_response

    payload = dict(base_response.data or {})
    age_exact = float(payload.get("age_exact") or 0.0)
    nav = payload.get("section16_navigation") or {}
    # Prefer canonical variant from /dashboard (matches is_teen_track + account_tier).
    _dv = nav.get("dashboard_variant")
    if _dv == "teen":
        is_teen = True
    elif _dv == "adult":
        is_teen = False
    else:
        is_teen = bool(13.0 <= age_exact <= 20.999)

    scan_access = payload.get("scan_access") or {}
    section4 = payload.get("section4_contract") or {}
    section5 = payload.get("section5_contract") or {}
    growth_projection = payload.get("growth_projection") or {}
    diagnostics = payload.get("posture_optimization_diagnostics") or {}
    streaks = payload.get("streaks") or {}

    display_lines = section5.get("display_lines") or {}
    base_height_cm = float(section4.get("base_height_cm") or growth_projection.get("current_height_cm") or 0.0)
    teen_genetic_cumulative_cm = float(section5.get("genetic_cumulative_cm") or 0.0)
    teen_posture_cumulative_cm = float(section5.get("postureplus_cumulative_cm") or 0.0)
    # Section 5 formulas:
    # Blue line  = Base + Genetic_Cumulative
    # Red line   = Base + Genetic_Cumulative + PosturePlus_Cumulative
    teen_genetic_cm = round(base_height_cm + teen_genetic_cumulative_cm, 4)
    teen_growthmax_cm = round(base_height_cm + teen_genetic_cumulative_cm + teen_posture_cumulative_cm, 4)
    # Fallback to legacy display lines only if cumulatives are absent.
    if teen_genetic_cm <= 0 and display_lines.get("blue_genetic_line_cm") is not None:
        teen_genetic_cm = float(display_lines.get("blue_genetic_line_cm") or 0.0)
    if teen_growthmax_cm <= 0 and display_lines.get("red_us_optimized_line_cm") is not None:
        teen_growthmax_cm = float(display_lines.get("red_us_optimized_line_cm") or teen_genetic_cm)
    teen_true_optimized_cm = display_lines.get("green_true_optimized_cm")
    try:
        teen_true_optimized_cm = float(teen_true_optimized_cm) if teen_true_optimized_cm is not None else None
    except Exception:
        teen_true_optimized_cm = None
    teen_daily_gain_cm = float(section5.get("daily_gains_today_cm") or 0.0)
    # Section 5.3 / 16.2 readouts: Genetic+ and Posture+ (GrowthMax+ product name) cards are *today* deltas (cm),
    # not cumulative line heights (those stay in teen_lines_cm / live_metrics).
    teen_genetic_plus_today_cm = float(section5.get("genetic_plus_today_cm") or 0.0)
    teen_posture_plus_today_cm = float(section5.get("posture_plus_today_cm") or 0.0)
    # Teen live height follows cumulative formula (not projected lifetime target).
    teen_height_live_cm = float(teen_growthmax_cm or base_height_cm)
    teen_live_blue_cm = float(teen_genetic_cm or base_height_cm)
    teen_live_red_cm = float(teen_growthmax_cm or base_height_cm)

    adult_base_cm = float(base_height_cm)
    adult_recovered_cm = float(section4.get("recovered_so_far_cm") or 0.0)
    adult_daily_gain_cm = float(section4.get("daily_gains_cm") or 0.0)
    adult_height_live_cm = float(section4.get("height_live_cm") or adult_base_cm)

    top_cards = [
        {"key": "base_height", "label": "Base Height", "value_cm": round(adult_base_cm, 4)},
        {"key": "total_recovered", "label": "Total Recovered", "value_cm": round(adult_recovered_cm, 4)},
        {"key": "daily_gains", "label": "Daily Gains", "value_cm": round(adult_daily_gain_cm, 4)},
        {"key": "height", "label": "Height", "value_cm": round(adult_height_live_cm, 4)},
    ]

    segments = diagnostics.get("segments") or {}

    section4_posture = section4.get("posture_exercises") or {}
    section8 = payload.get("section8_mapping_summary") or {}
    teen_map = section8.get("teen_dashboard_mapping") or {}
    adult_map = section8.get("adult_dashboard_mapping") or {}
    teen_nutrition_dots = int(teen_map.get("teen_nutrition_dots") or 0)
    teen_lifestyle_dots = int(teen_map.get("teen_lifestyle_dots") or 0)
    # Section 5.10 — single formula for combined % (same as section8 teen_dashboard_mapping).
    teen_lifestyle_nutrition_pct = (
        teen_lifestyle_nutrition_combined_percent(teen_nutrition_dots, teen_lifestyle_dots)
        if is_teen
        else None
    )
    _pb_src = (teen_map if is_teen else adult_map).get("progress_bars_percent") or {}
    if isinstance(_pb_src, dict) and _pb_src:
        posture_bars = {str(k): int(v) for k, v in _pb_src.items()}
    else:
        posture_bars = {
            seg: int((seg_payload or {}).get("percent_optimized", 0) or 0)
            for seg, seg_payload in segments.items()
        }
    today_streak = int(((streaks.get("health") or {}).get("current_streak") or 0))
    leaderboard = streaks.get("leaderboard") or {}
    # `get_user_leaderboard_rank()` returns `my_rank` / `total_rank` (not `rank`).
    rank_value = None
    if isinstance(leaderboard, dict):
        rank_value = leaderboard.get("my_rank", None)
        if rank_value is None:
            rank_value = leaderboard.get("total_rank", None)

    include_debug = str(request.query_params.get("include_debug", "")).lower() in {"1", "true", "yes"}
    profile_gender = str((payload.get("profile") or {}).get("gender") or "male").strip().lower()
    if profile_gender not in {"male", "female"}:
        profile_gender = "male"
    teen_locked_post_day7 = bool(
        is_teen
        and bool((payload.get("subscription") or {}).get("is_paid") is False)
        and bool(payload.get("full_access_trial_expired"))
    )
    # Spec (Sections 5.5 / 7.2 / 11.5): post-day-7 unpaid teen red line (and height card)
    # must flatline at the trial-end snapshot while blue continues to rise.
    if teen_locked_post_day7 and display_lines.get("red_us_optimized_line_cm") is not None:
        try:
            teen_live_red_cm = float(display_lines.get("red_us_optimized_line_cm") or teen_live_red_cm)
            teen_height_live_cm = float(teen_live_red_cm)
            teen_growthmax_cm = float(teen_live_red_cm)
        except Exception:
            logger.exception("Failed applying teen_locked_post_day7 red-line override")
    # Spec (Section 5.6 / 7.2): True Optimized Height is revealed ONLY when paid (not during trial).
    can_view_true_optimized = bool(is_teen and bool((payload.get("subscription") or {}).get("is_paid", False)))
    teen_scan_required = bool(scan_access.get("teen_scan_required", False))
    true_optimized_locked = bool(display_lines.get("green_true_optimized_locked", False) or teen_locked_post_day7)
    teen_scan_completed = bool(scan_access.get("scan_completed"))
    anomalies = []
    # Build target metrics from growth projection (forecast model).
    try:
        teen_target_blue_cm = float(growth_projection.get("estimated_genetic_height_cm") or 0.0)
    except Exception:
        logger.exception("Failed parsing estimated_genetic_height_cm", extra={"value": repr(growth_projection.get("estimated_genetic_height_cm"))})
        teen_target_blue_cm = 0.0
    try:
        teen_target_red_cm = float(growth_projection.get("optimized_estimated_genetic_height_cm") or 0.0)
    except Exception:
        logger.exception("Failed parsing optimized_estimated_genetic_height_cm", extra={"value": repr(growth_projection.get("optimized_estimated_genetic_height_cm"))})
        teen_target_red_cm = 0.0
    if teen_target_blue_cm <= 0:
        teen_target_blue_cm = teen_live_blue_cm
    if teen_target_red_cm <= 0:
        teen_target_red_cm = teen_target_blue_cm
    # Target invariants: optimized (red) must not be below genetic (blue).
    teen_target_red_cm = max(teen_target_red_cm, teen_target_blue_cm)
    try:
        teen_target_unoptimized_cm = float(growth_projection.get("unoptimized_estimated_genetic_height_cm") or 0.0)
    except Exception:
        logger.exception("Failed parsing unoptimized_estimated_genetic_height_cm", extra={"value": repr(growth_projection.get("unoptimized_estimated_genetic_height_cm"))})
        teen_target_unoptimized_cm = 0.0
    if teen_target_unoptimized_cm <= 0:
        teen_target_unoptimized_cm = max(0.0, teen_target_blue_cm - 2.0)
    # Unoptimized must not exceed genetic target.
    teen_target_unoptimized_cm = min(teen_target_unoptimized_cm, teen_target_blue_cm)

    # Do not flag \"zero cumulative\" as anomalous unless we have actual ledger history.
    if (
        is_teen
        and teen_scan_completed
        and (HeightLedger.objects.filter(user=request.user, entry_type="daily_compute").exists())
        and teen_genetic_cumulative_cm <= 0
        and teen_posture_cumulative_cm <= 0
    ):
        anomalies.append("cumulative_zero_with_scan_completed")
    if is_teen and abs(teen_target_red_cm - teen_live_red_cm) > 5.0:
        anomalies.append("target_live_gap_large")
    if is_teen and teen_scan_required:
        anomalies.append("scan_required_pending_baseline")

    # Display mode:
    # - live: show Base+cum values
    # - target_projection_fallback: show projection lines if live cumulatives are missing/abnormal
    teen_display_mode = "live"
    if is_teen and teen_scan_required:
        teen_display_mode = "pending_scan_baseline"
    if is_teen and teen_scan_completed and "cumulative_zero_with_scan_completed" in anomalies and teen_target_red_cm > (teen_live_red_cm + 1.0):
        teen_display_mode = "target_projection_fallback"

    if is_teen and teen_display_mode == "target_projection_fallback":
        teen_card_genetic_cm = teen_target_blue_cm
        teen_card_growthmax_cm = teen_target_red_cm
        # Spec: the teen \"Height\" card is the current displayed height (live), not the target.
        teen_card_height_cm = teen_live_red_cm
    else:
        teen_card_genetic_cm = teen_live_blue_cm
        teen_card_growthmax_cm = teen_live_red_cm
        teen_card_height_cm = teen_live_red_cm
    local_today = user_today(user)
    teen_ga_cm = (
        round(float(compute_genetic_average_cm(user, local_today)), 4) if is_teen else None
    )
    teen_daily_ga_gain = (
        round(float(compute_daily_genetic_average_gain_cm(user, local_today)), 6)
        if is_teen
        else None
    )
    if is_teen:
        habits_logged_count = int(min(8, teen_nutrition_dots + teen_lifestyle_dots))
    else:
        ap = int(section4.get("posture_nutrition_percent") or 0)
        habits_logged_count = int(max(0, min(4, ap // 25)))

    if is_teen:
        top_cards = [
            {
                "key": "genetic_plus",
                "label": "Genetic +",
                "value_cm": round(teen_genetic_plus_today_cm, 4),
            },
            {
                "key": "posture_plus",
                "label": "Posture+",
                "value_cm": round(teen_posture_plus_today_cm, 4),
            },
            {"key": "daily_gains", "label": "Daily Gains", "value_cm": round(teen_daily_gain_cm, 4)},
            {"key": "height", "label": "Height", "value_cm": round(teen_card_height_cm, 4)},
        ]

    # Canonical teen line model for dashboard + chart:
    # blue = genetic line, red = us optimized, green = true optimized (paid/trial only).
    teen_chart_genetic_cm = teen_target_blue_cm if is_teen else teen_live_blue_cm
    teen_chart_optimized_cm = (
        teen_true_optimized_cm
        if (is_teen and teen_true_optimized_cm is not None and not true_optimized_locked)
        else teen_target_red_cm
    )
    teen_chart_unoptimized_cm = teen_target_unoptimized_cm
    canonical_chart = payload.get("chart_breakdown")
    adult_target_height_cm = float(section4.get("target_height_cm") or adult_height_live_cm or adult_base_cm)
    try:
        adult_estimated_genetic_cm = float(
            growth_projection.get("estimated_genetic_height_cm") or adult_base_cm
        )
    except Exception:
        adult_estimated_genetic_cm = float(adult_base_cm)
    adult_optimized_estimated_cm = float(max(adult_target_height_cm, adult_estimated_genetic_cm))
    # Spec adult dashboard does not use teen-style genetic projection comparisons.
    adult_unoptimized_cm = None
    adult_diff_cm = None
    adult_genetic_status = None
    if is_teen:
        try:
            canonical_chart = calculate_height_projection(
                teen_height_live_cm,
                teen_chart_optimized_cm,
                teen_chart_genetic_cm,
                teen_chart_unoptimized_cm,
                profile_gender,
            )
        except Exception:
            canonical_chart = payload.get("chart_breakdown")
    else:
        # Spec (Section 16.2 adult dashboard): days-based recovery chart (current vs target),
        # not the teen 13–21 genetic projection curve.
        try:
            days_window = 90
            # Use ledger history if present; fall back to a flat line at current height.
            rows = list(
                HeightLedger.objects.filter(user=request.user, entry_type="daily_compute")
                .order_by("-log_date", "-created_at")[:days_window]
            )
            rows = list(reversed(rows))
            series = []
            for idx, r in enumerate(rows):
                series.append(
                    {
                        "day": idx,
                        "date": str(r.log_date),
                        "current_height_cm": round(float(r.cumulative_um or 0) / 10000.0, 4),
                        "target_height_cm": round(adult_target_height_cm, 4),
                    }
                )
            if not series:
                series = [
                    {
                        "day": 0,
                        "date": None,
                        "current_height_cm": round(float(adult_height_live_cm), 4),
                        "target_height_cm": round(adult_target_height_cm, 4),
                    }
                ]
            max_y = max(
                max(p["current_height_cm"] for p in series),
                max(p["target_height_cm"] for p in series),
            )
            canonical_chart = {
                "x_axis": "days",
                "series": series,
                "maxY": int(((max_y + 10) // 10) * 10),
            }
        except Exception:
            canonical_chart = payload.get("chart_breakdown")

    dashboard = {
        "variant": "teen" if is_teen else "adult",
        "calculation_mode": teen_display_mode if is_teen else "adult_live",
        "anomalies": anomalies if is_teen else [],
        "genetic_average_cm": teen_ga_cm,
        "daily_genetic_average_gain_cm": teen_daily_ga_gain,
        "profile": {
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            "age": (payload.get("profile") or {}).get("age"),
            "gender": (payload.get("profile") or {}).get("gender"),
            "base_height_cm": section4.get("base_height_cm"),
            "account_tier": payload.get("account_tier"),
        },
        "live_metrics": (
            {
                "base_height_cm": round(base_height_cm, 4),
                "genetic_blue_cm": round(teen_live_blue_cm, 4),
                "us_optimized_red_cm": round(teen_live_red_cm, 4),
                "height_cm": round(teen_live_red_cm, 4),
                "daily_gains_cm": round(teen_daily_gain_cm, 4),
                "genetic_cumulative_cm": round(teen_genetic_cumulative_cm, 4),
                "postureplus_cumulative_cm": round(teen_posture_cumulative_cm, 4),
            } if is_teen else {
                "base_height_cm": round(adult_base_cm, 4),
                "total_recovered_cm": round(adult_recovered_cm, 4),
                "daily_gains_cm": round(adult_daily_gain_cm, 4),
                "height_cm": round(adult_height_live_cm, 4),
            }
        ),
        "target_metrics": (
            {
                "genetic_blue_cm": round(teen_target_blue_cm, 4),
                "us_optimized_red_cm": round(teen_target_red_cm, 4),
                "unoptimized_cm": round(teen_target_unoptimized_cm, 4),
                "true_optimized_green_cm": (
                    round(teen_true_optimized_cm, 4) if (teen_true_optimized_cm is not None and not true_optimized_locked) else None
                ),
            } if is_teen else {
                "target_height_cm": section4.get("target_height_cm"),
            }
        ),
        "scan": {
            "scan_completed": bool(scan_access.get("scan_completed")),
            "can_scan": bool(scan_access.get("can_scan")) and (not teen_locked_post_day7),
            "scan_message": (
                "Unlock full Posture+, ultra-accurate True Optimized Height, and unlimited re-scans."
                if teen_locked_post_day7 else scan_access.get("scan_message")
            ),
            "rescan_timer_days": scan_access.get("Re_Scan_Timer"),
            "teen_scan_required": bool(scan_access.get("teen_scan_required", False)),
        },
        "top_graph": {
            "cards": top_cards,
            "teen_lines_cm": {
                # Spec (Section 16.2 teen): chart legend lines are the target endpoints,
                # not the live \"Height\" readout (which stays in cards/live_metrics).
                "genetic_blue": round(teen_target_blue_cm, 4),
                "us_optimized_red": round(teen_target_red_cm, 4),
                "true_optimized_green": (
                    round(teen_true_optimized_cm, 4) if (teen_true_optimized_cm is not None and not true_optimized_locked) else None
                ),
                "true_optimized_locked": true_optimized_locked,
            } if is_teen else None,
            "adult_target_height_cm": section4.get("target_height_cm") if not is_teen else None,
        },
        "routine_progress": {
            "cta": nav.get("primary_cta") or "Start Today's Routine",
            "posture_exercises_fraction": section4_posture.get("fraction_today"),
            "posture_exercises_done": int(section4_posture.get("completed_total_today") or 0),
            "posture_exercises_total": int(section4_posture.get("assigned_total") or 0),
            "exercises_done": int(section4_posture.get("completed_total_today") or 0),
            "total_exercises": int(section4_posture.get("assigned_total") or 0),
            "habits_logged": habits_logged_count,
            "posture_exercises_percent": (
                int(
                    round(
                        (
                            (int(section4_posture.get("completed_total_today") or 0) / max(1, int(section4_posture.get("assigned_total") or 0)))
                            * 100.0
                        )
                    )
                )
                if int(section4_posture.get("assigned_total") or 0) > 0
                else 0
            ),
            "nutrition_percent": (
                int(teen_lifestyle_nutrition_pct)
                if is_teen
                else int(section4.get("posture_nutrition_percent") or 0)
            ),
            "teen_nutrition_dots": teen_nutrition_dots if is_teen else None,
            "teen_lifestyle_dots": teen_lifestyle_dots if is_teen else None,
            "streak_days": today_streak,
            "daily_points": int(payload.get("today_total_score") or 0),
            "rank": rank_value,
        },
        "posture_optimization": {
            "total_recoverable_loss_cm": diagnostics.get("total_recoverable_loss_cm"),
            "total_current_loss_cm": diagnostics.get("total_current_loss_cm"),
            "bars_percent": posture_bars,
            "raw_segments": segments,
        },
        "ai_analysis": payload.get("ai_analysis") or {},
        "chart_breakdown": canonical_chart,
        "subscription": payload.get("subscription") or {},
        "trial_data": {
            "is_teen": bool(is_teen),
            "is_trial": bool((payload.get("subscription") or {}).get("is_trial", False)),
            "trial_day": payload.get("trial_day"),
            "trial_start": (payload.get("subscription") or {}).get("trial_start"),
            "trial_end": (payload.get("subscription") or {}).get("trial_end"),
            "full_access_trial_active": bool(payload.get("full_access_trial_active")),
            "full_access_trial_expired": bool(payload.get("full_access_trial_expired")),
        },
        "important_data": {
            "growth_projection": {
                "current_height_cm": (
                    round(teen_live_red_cm, 4) if is_teen
                    else round(adult_height_live_cm, 4)
                ),
                "estimated_genetic_height_cm": (
                    round(teen_chart_genetic_cm, 4) if is_teen
                    else None
                ),
                "optimized_estimated_genetic_height_cm": (
                    round(teen_chart_optimized_cm, 4) if is_teen
                    else None
                ),
                "unoptimized_estimated_genetic_height_cm": (
                    round(teen_chart_unoptimized_cm, 4) if is_teen
                    else None
                ),
                "genetic_height_difference": (
                    round(teen_height_live_cm - teen_chart_genetic_cm, 4) if is_teen
                    else None
                ),
                "genetic_status": (
                    "equal_estimated_genetic_height" if is_teen and round(teen_height_live_cm - teen_chart_genetic_cm, 4) == 0
                    else (
                        "below_estimated_genetic_height" if is_teen and teen_height_live_cm < teen_chart_genetic_cm
                        else (
                            "above_estimated_genetic_height" if is_teen and teen_height_live_cm > teen_chart_genetic_cm
                            else None
                        )
                    )
                ),
            },
            "subscription": payload.get("subscription") or {},
            "response_data": (
                {
                    "tier": (payload.get("response_data") or {}).get("tier"),
                    "genetic_height_cm": round(teen_chart_genetic_cm, 4),
                    "current_height_cm": round(teen_height_live_cm, 4),
                    "optimized_height_cm": (
                        None if (teen_locked_post_day7 or (not can_view_true_optimized)) else round(teen_chart_optimized_cm, 4)
                    ),
                    "can_rescan": bool(scan_access.get("can_scan")) and (not teen_locked_post_day7),
                    "growth_max_active": bool(not true_optimized_locked),
                    "days_since_scan": scan_access.get("days_since_scan"),
                } if is_teen else {
                    "tier": (payload.get("response_data") or {}).get("tier", "adult"),
                    "current_height_cm": round(adult_height_live_cm, 4),
                    "target_height_cm": round(adult_target_height_cm, 4),
                    "height_reclaimed_cm": round(adult_recovered_cm, 4),
                    "remaining_cm": round(max(0.0, adult_target_height_cm - adult_height_live_cm), 4),
                    "can_rescan": bool(scan_access.get("can_scan")),
                    "ai_assistant": bool((payload.get("response_data") or {}).get("ai_assistant", True)),
                    "days_since_scan": scan_access.get("days_since_scan"),
                }
            ),
            "posture_source": payload.get("posture_source"),
            "last_scan": payload.get("last_scan"),
        },
        "meta": {
            "screen_state": (
                "dashboard_teen_locked_post_trial"
                if (is_teen and teen_locked_post_day7)
                else nav.get("current_screen_state")
            ),
            "age_exact": payload.get("age_exact"),
            "account_tier": payload.get("account_tier"),
            "trial_day": payload.get("trial_day"),
            "full_access_trial_active": payload.get("full_access_trial_active"),
            "full_access_trial_expired": payload.get("full_access_trial_expired"),
        },
    }

    if include_debug:
        dashboard["debug"] = {
            "section4_contract": section4,
            "section5_contract": section5,
            "scan_access": scan_access,
            "streaks": streaks,
        }

    response_payload = {
        "message": "Dashboard retrieved successfully",
        "dashboard": dashboard,
    }
    serializer = DashboardNewResponseSerializer(data=response_payload)
    serializer.is_valid(raise_exception=True)
    return Response(serializer.validated_data, status=status.HTTP_200_OK)