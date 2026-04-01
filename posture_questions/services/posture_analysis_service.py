from typing import Dict, Any, Optional
import json
from django.utils import timezone
from django.forms.models import model_to_dict
from posture_questions.models import PostureQuestion
from posture.models import PostureReport
from posture_analysis.models import UserPosturalOptimizationData
from posture_analysis.serializers import UserPosturalOptimizationDataSerializer
from utils.chatgpt_service import generate_chatgpt_response
from utils.ai_analysis import save_ai_analysis
from utils.posture_optimizer import calculate_optimization_breakdown


class PostureAnalysisService:
    """Service for handling posture analysis and AI-powered recommendations"""
    
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

    # Share of posture gains per segment
    POSTURE_SEGMENT_SPLIT: Dict[str, float] = {
        "spinal_compression": 0.30,
        "posture_collapse":   0.35,
        "pelvic_tilt_back":   0.25,
        "leg_hamstring":      0.10,
    }

    @staticmethod
    def annual_growth_percent(age: int) -> float:
        """Get annual growth percentage for given age"""
        return PostureAnalysisService.AGE_GROWTH.get(age, 0.0)

    @staticmethod
    def daily_genetic_gain_cm(height_cm: float, age: int) -> float:
        """Calculate daily genetic gain in cm"""
        return height_cm * PostureAnalysisService.annual_growth_percent(age) / 365.0

    @staticmethod
    def posture_gain_cm_from_points(points: int | float) -> float:
        """Convert posture points to cm gain"""
        return points * 0.001  # 1 point = 0.001 cm

    @staticmethod
    def get_posture_analysis(user, profile_dict: Dict[str, Any], rescan: Optional[str] = None) -> tuple:
        """Get or generate posture analysis for user"""
        posture_report = PostureReport.objects.filter(user=user).order_by('-created_at').first()

        if posture_report and posture_report.data:
            return PostureAnalysisService._extract_from_report(posture_report)
        else:
            return PostureAnalysisService._generate_new_analysis(user, profile_dict, rescan)

    @staticmethod
    def _extract_from_report(posture_report) -> tuple:
        """Extract analysis data from existing posture report"""
        mdata = posture_report.data or {}
        ai_analysis = mdata.get("summary")
        optimization_breakdown = mdata.get("optimization_breakdown")

        # Fallback to nested "analysis" block if top-level keys not found
        if ai_analysis is None or optimization_breakdown is None:
            analysis_data = mdata.get("analysis", {})
            ai_analysis = ai_analysis or analysis_data.get("summary")
            optimization_breakdown = optimization_breakdown or analysis_data.get("optimization_breakdown")
        
        return ai_analysis, optimization_breakdown

    @staticmethod
    def _generate_new_analysis(user, profile_dict: Dict[str, Any], rescan: Optional[str] = None) -> tuple:
        """Generate new AI analysis for user's posture"""
        try:
            if rescan == "yes":
                raise UserPosturalOptimizationData.DoesNotExist

            user_data = UserPosturalOptimizationData.objects.get(user=user)
            serializer = UserPosturalOptimizationDataSerializer(user_data)
            ai_analysis = serializer.data

        except UserPosturalOptimizationData.DoesNotExist:
            prompt = PostureAnalysisService._build_analysis_prompt(user, profile_dict)
            # gpt_response = generate_chatgpt_response(prompt, system_role="You are a health and posture expert.")

            #  prompt = PostureAnalysisService._build_analysis_prompt(user, profile_dict)

            MAX_RETRIES = 5
            gpt_response = None

            for attempt in range(MAX_RETRIES):

                gpt_response = generate_chatgpt_response(
                    prompt,
                    system_role="You are a health and posture expert."
                )

                if not gpt_response:
                    continue

                posture = gpt_response.get("postural_optimization", {})

                spinal = float(posture.get("spinal_compression", 0) or 0)
                collapse = float(posture.get("posture_collapse", 0) or 0)
                pelvic = float(posture.get("pelvic_tilt_back", 0) or 0)
                leg = float(posture.get("leg_hamstring", 0) or 0)

                values = [spinal, collapse, pelvic, leg]
                print('attempt')
                print(attempt)
                # Stop retry if any value > 0
                if any(v > 0 for v in values):
                    break

            
            # Update last scan time
            from user_profile.models import UserProfile
            if rescan == "yes":
                profile = UserProfile.objects.get(user=user)
                profile.last_scan = timezone.now()
                profile.save()

            if gpt_response:
                user_data = save_ai_analysis(user, gpt_response)
                serializer = UserPosturalOptimizationDataSerializer(user_data)
                ai_analysis = serializer.data
            else:
                ai_analysis = None

        optimization_breakdown = calculate_optimization_breakdown(ai_analysis)
        return ai_analysis, optimization_breakdown

    @staticmethod
    # def _build_analysis_prompt(user, profile_dict: Dict[str, Any]) -> str:
    #     """Build GPT prompt for posture analysis"""
    #     posture_q = PostureQuestion.objects.filter(user=user).first()
    #     if not posture_q:
    #         raise ValueError("Posture Question data not found.")

    #     posture_dict: Dict[str, Any] = model_to_dict(posture_q)

    #     # Build questionnaire structure
    #     questionnaire_full = {}
    #     for field, value in posture_dict.items():
    #         if field.endswith(("_question", "_options", "_answer")):
    #             base, suffix = field.rsplit("_", 1)
    #             questionnaire_full.setdefault(base, {})[suffix] = value

    #     q = posture_dict
    #     questionnaire_scores = {
    #         "forward_head_posture": q.get("forward_head_posture_answer"),
    #         "lower_back_gap":       q.get("gap_between_your_lower_back_answer"),
    #         "back_tightness":       q.get("tightness_or_discomfort_answer"),
    #         "slouching":            q.get("slouch_when_standing_or_sitting_answer"),
    #         "end_of_day_height":    q.get("feel_noticeably_shorter_end_of_day_compare_to_morning_answer"),
    #         "alignment":            q.get("perfectly_aligned_and_decompressed_answer"),
    #         "hamstring_flexibility":q.get("flexible_in_your_hamstrings_and_hips_answer"),
    #         "core_activation":      q.get("active_your_core_during_daily_task_answer"),
    #     }

    #     # Get formatted heights
    #     from .height_helpers import height_str, fmt_cm, ft_in_to_cm
        
    #     current_height = height_str(profile_dict.get("current_height_foot"), profile_dict.get("current_height_inch"))
    #     ideal_height = height_str(profile_dict.get("ideal_height_foot"), profile_dict.get("ideal_height_inch"))
    #     father_height = height_str(profile_dict.get("father_height_foot"), profile_dict.get("father_height_inch"))
    #     mother_height = height_str(profile_dict.get("mother_height_foot"), profile_dict.get("mother_height_inch"))

    #     dad_cm = ft_in_to_cm(profile_dict.get("father_height_foot"), profile_dict.get("father_height_inch"))
    #     mom_cm = ft_in_to_cm(profile_dict.get("mother_height_foot"), profile_dict.get("mother_height_inch"))

    #     gender = (profile_dict.get("gender") or "").strip().lower()
    #     mph_cm = None
    #     if dad_cm is not None and mom_cm is not None:
    #         mph_cm = (dad_cm + mom_cm + 13) / 2 if gender == "male" else (dad_cm + mom_cm - 13) / 2

    #     mph_cm_display = fmt_cm(mph_cm)
    #     shoe_size_display = profile_dict.get("shoe_size", "not provided")
    #     posture_points_today = profile_dict.get("posture_points_today", 0)

    #     # • Weight: {profile_dict['current_weight']} Shoe size: {shoe_size_display}  
    #     # • Activity level: {profile_dict['activity_level_answer']}  
    #     # • Sitting hours/day: {profile_dict['sitting_hours_answer']}  
    #     # • Sleep: {profile_dict['sleep_quality_and_position_answer_one']} h  \
    #     # Position: {profile_dict['sleep_quality_and_position_answer_two']}  
    #     # • Flexibility: {profile_dict['posture_and_flexibility_answer_one']}, \
    #     # {profile_dict['posture_and_flexibility_answer_two']}, \
    #     # {profile_dict['posture_and_flexibility_answer_three']}  

    #     prompt = f"""
    #         You are a certified physiotherapist and posture expert. Your job is to analyze the user's posture-related questionnaire and physical profile to provide accurate, scientific feedback.

    #         TASK 1 Posture Summary and Recommendations  
    #         Based on the user's answers and profile data:
    #         • Write a short summary of their posture condition.  
    #         • Provide 5 personalized recommendations (each with a title and 1-2 sentence description).  
    #         • Estimate a realistic "max_height_gain_inches" from posture correction alone (typically 0 to 1.5 inches).  
    #         • Add a short note to remind the user that genetic factors and professional supervision matter.

    #         TASK 2 Postural Optimization Breakdown  
    #         Use the 8 posture-related answers (SECOND JSON block) to assign scores from 0–100 (where 100 = major issue and 0 = no issue) for:
    #         1. spinal_compression  
    #         2. posture_collapse  
    #         3. pelvic_tilt_back  
    #         4. leg_hamstring  

    #         Use the meaning or severity of the answers to distribute scores proportionally. For example, "severe slouching" or "constant tightness" should result in a high percentage.

    #         TASK 3 Growth Potential Analysis  
    #         Use the profile data to:
    #         • Estimate the user's **daily genetic growth potential (cm/day)** based on age and current height.  
    #         • Estimate their **daily posture-based gain (cm/day)** using posture_points_today.  
    #         • Break posture-based gain into 4 parts using the segment gain split (see POSTURE SEGMENT SPLIT).

    #         ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #         QUESTIONNAIRE FULL (question / options / answer):
    #         {json.dumps(questionnaire_full, indent=2, ensure_ascii=False)}

    #         POSTURE SCORES (8 answers):
    #         {json.dumps(questionnaire_scores, indent=2, ensure_ascii=False)}

    #         PROFILE DATA:
    #         • Age: {profile_dict['age']}  Gender: {profile_dict['gender']}  
    #         • Current height: {current_height}  Ideal height: {ideal_height}  
    #         • Father height: {father_height}  Mother height: {mother_height}  
    #         • Estimated genetic height: {mph_cm_display}  
            
    #         • Posture Points Today: {posture_points_today}  

    #         POSTURE SEGMENT SPLIT (use for gain distribution):
    #         {json.dumps(PostureAnalysisService.POSTURE_SEGMENT_SPLIT, indent=2)}

    #         ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    #         ### OUTPUT FORMAT (JSON only)

    #         {{
    #         "summary": "...",
    #         "recommendations": [
    #             {{ "title": "...", "description": "..." }}
    #         ],
    #         "max_height_gain_inches": 0.0,
    #         "note": "...",
    #         "postural_optimization": {{
    #             "spinal_compression": 0,
    #             "posture_collapse": 0,
    #             "pelvic_tilt_back": 0,
    #             "leg_hamstring": 0
    #         }}
    #         }}
    #         """
    #     return prompt

    @staticmethod
    def _build_analysis_prompt(user, profile_dict: Dict[str, Any]) -> str:
        """Build GPT prompt for posture analysis"""

        age = profile_dict.get("age")

        posture_q = PostureQuestion.objects.filter(user=user).first()

        questionnaire_full = {}
        questionnaire_scores = {}

        if posture_q:
            posture_dict: Dict[str, Any] = model_to_dict(posture_q)

            # Build questionnaire structure
            for field, value in posture_dict.items():
                if field.endswith(("_question", "_options", "_answer")):
                    base, suffix = field.rsplit("_", 1)
                    questionnaire_full.setdefault(base, {})[suffix] = value

            q = posture_dict

            questionnaire_scores = {
                "forward_head_posture": q.get("forward_head_posture_answer"),
                "lower_back_gap": q.get("gap_between_your_lower_back_answer"),
                "back_tightness": q.get("tightness_or_discomfort_answer"),
                "slouching": q.get("slouch_when_standing_or_sitting_answer"),
                "end_of_day_height": q.get(
                    "feel_noticeably_shorter_end_of_day_compare_to_morning_answer"
                ),
                "alignment": q.get("perfectly_aligned_and_decompressed_answer"),
                "hamstring_flexibility": q.get(
                    "flexible_in_your_hamstrings_and_hips_answer"
                ),
                "core_activation": q.get("active_your_core_during_daily_task_answer"),
            }

        # height helpers
        from .height_helpers import height_str, fmt_cm, ft_in_to_cm

        current_height = height_str(
            profile_dict.get("current_height_foot"),
            profile_dict.get("current_height_inch"),
        )

        ideal_height = height_str(
            profile_dict.get("ideal_height_foot"),
            profile_dict.get("ideal_height_inch"),
        )

        father_height = height_str(
            profile_dict.get("father_height_foot"),
            profile_dict.get("father_height_inch"),
        )

        mother_height = height_str(
            profile_dict.get("mother_height_foot"),
            profile_dict.get("mother_height_inch"),
        )

        dad_cm = ft_in_to_cm(
            profile_dict.get("father_height_foot"),
            profile_dict.get("father_height_inch"),
        )

        mom_cm = ft_in_to_cm(
            profile_dict.get("mother_height_foot"),
            profile_dict.get("mother_height_inch"),
        )

        gender = (profile_dict.get("gender") or "").strip().lower()

        mph_cm = None
        if dad_cm and mom_cm:
            if gender == "male":
                mph_cm = (dad_cm + mom_cm + 13) / 2
            else:
                mph_cm = (dad_cm + mom_cm - 13) / 2

        mph_cm_display = fmt_cm(mph_cm)

        shoe_size_display = profile_dict.get("shoe_size", "not provided")
        posture_points_today = profile_dict.get("posture_points_today", 0)

        # posture section control
        posture_section = ""

        if posture_q:
            posture_section = f"""
            POSTURE ANSWERS:

            {json.dumps(questionnaire_scores, indent=2)}
            """
        else:
            posture_section = """
            POSTURE ANSWERS:

            User has not completed posture questionnaire.
            Provide general posture recommendations based on profile.
            """

        prompt = f"""
            You are a certified physiotherapist and posture expert.

            Analyze the user's posture, lifestyle, and growth potential.

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            TASK 1 — Posture Summary

            • Write a short summary of the user's posture condition.
            • Provide 5 recommendations.
            • Estimate possible height gain from posture correction (0–1.5 inches).
            • Mention that genetics and age influence results.

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            TASK 2 — Postural Optimization Breakdown

            Provide severity scores (0–100):

            - spinal_compression
            - posture_collapse
            - pelvic_tilt_back
            - leg_hamstring

            If posture questionnaire is missing, estimate based on typical posture patterns.

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            PROFILE DATA

            Age: {profile_dict.get("age")}
            Gender: {profile_dict.get("gender")}

            Current Height: {current_height}
            Ideal Height: {ideal_height}

            Father Height: {father_height}
            Mother Height: {mother_height}

            Estimated Genetic Height: {mph_cm_display}

            Shoe Size: {shoe_size_display}

            Posture Points Today: {posture_points_today}

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            QUESTIONNAIRE FULL:

            {json.dumps(questionnaire_full, indent=2)}

            {posture_section}

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            POSTURE SEGMENT SPLIT

            {json.dumps(PostureAnalysisService.POSTURE_SEGMENT_SPLIT, indent=2)}

            ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

            OUTPUT FORMAT (JSON ONLY)

            {{
            "summary": "...",

            "recommendations": [
            {{"title": "...", "description": "..."}}
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

        return prompt

    @staticmethod
    def calculate_segment_gains(posture_points_today: int | float) -> Dict[str, float]:
        """Calculate segment gains based on posture points"""
        daily_posture_gain_cm = PostureAnalysisService.posture_gain_cm_from_points(posture_points_today)
        
        segment_gains_today = {
            seg: round(daily_posture_gain_cm * frac, 4)
            for seg, frac in PostureAnalysisService.POSTURE_SEGMENT_SPLIT.items()
        }
        
        return segment_gains_today
