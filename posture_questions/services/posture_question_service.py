from typing import Dict, Any
from django.forms.models import model_to_dict
from posture_questions.models import PostureQuestion


class PostureQuestionService:
    """Service for managing posture questionnaire data"""
    
    ALLOWED_FIELDS = [
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

    @staticmethod
    def upsert_posture_questions(user, request_data: Dict[str, Any]) -> tuple:
        """Create or update posture questions for user
        
        Returns:
            tuple: (posture_question_data, created)
        """
        update_data = {
            field: request_data[field] 
            for field in PostureQuestionService.ALLOWED_FIELDS 
            if field in request_data
        }

        posture_question, created = PostureQuestion.objects.update_or_create(
            user=user,
            defaults=update_data
        )

        posture_question_data = model_to_dict(posture_question)
        
        return posture_question_data, created

    @staticmethod
    def get_posture_questions(user) -> PostureQuestion:
        """Get posture questions for user"""
        return PostureQuestion.objects.filter(user=user).first()
