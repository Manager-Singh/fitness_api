import json
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from user_profile.models import UserProfile
from posture_questions.models import PostureQuestion
from posture_analysis.models import UserPosturalOptimizationData
from .models import ChatMessage
from utils.chatgpt_service import generate_chatgpt_response
from utils.nlp_tools import get_sentence_embedding, hybrid_similarity, normalize

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_chat(request):
    user = request.user
    message = request.data.get("message")
    if not message:
        return Response({"error": "Message required"}, status=400)

    # Normalize message
    normalized_message = normalize(message)

    # Step 1: Generate current message embedding
    current_vector = get_sentence_embedding(normalized_message)

    # Step 2: Search similar past messages
    threshold = 0.82  # Slightly relaxed threshold
    past_messages = ChatMessage.objects.filter(user=user).exclude(question_vector=None)
    for past in past_messages:
        try:
            past_vector = json.loads(past.question_vector)
            similarity = hybrid_similarity(normalized_message, normalize(past.user_message), current_vector, past_vector)
            if similarity >= threshold:
                return Response({
                    "user_message": message,
                    "ai_reply": past.ai_response,
                    "cached": True,
                    "similarity": round(similarity, 3),
                    "source": "cache"
                })
        except Exception:
            continue  # Skip invalid vector entries

    def p(v): return v if v else "not provided"

    # User Profile Context
    try:
        profile = UserProfile.objects.get(user=user)
        profile_context = (
            f"Age: {p(profile.age)}, Gender: {p(profile.gender)}, Height: {p(profile.current_height_cm)} cm, "
            f"Goal: {p(profile.main_goal_with_heightmax_answer)}, Activity: {p(profile.activity_level_answer)}"
        )
    except:
        profile_context = "Profile data not available."

    # Posture Questions
    try:
        posture = PostureQuestion.objects.get(user=user)
        posture_context = (
            f"Forward Head: {p(posture.forward_head_posture_answer)}, "
            f"Slouching: {p(posture.slouch_when_standing_or_sitting_answer)}, "
            f"Hamstring Flexibility: {p(posture.flexible_in_your_hamstrings_and_hips_answer)}"
        )
    except:
        posture_context = "Posture questionnaire not available."

    # AI Optimization Data
    try:
        ai_data = UserPosturalOptimizationData.objects.get(user=user)
        ai_context = (
            f"AI Summary: {ai_data.summary}. Max gain: {ai_data.max_height_gain_inches} inches. "
            f"Spinal: {ai_data.spinal_compression}%, Collapse: {ai_data.posture_collapse}%, "
            f"Pelvic: {ai_data.pelvic_tilt_back}%, Hamstring: {ai_data.leg_hamstring}%"
        )
    except:
        ai_context = "No AI optimization data."

    # Full Context
    full_context = f"{profile_context}\n{posture_context}\n{ai_context}"

    # Generate ChatGPT response
    try:
        response = generate_chatgpt_response(
            message,
            system_role=f"You are a posture and height optimization assistant and compare my profile and return response in 50 - 60 words.\n{full_context}"
        )

        reply = response.get("raw_content")
        if not reply:
            return Response({"error": "AI response not generated."}, status=500)

        # Save new chat and vector as JSON string
        ChatMessage.objects.create(
            user=user,
            user_message=message,
            ai_response=reply,
            question_vector=json.dumps(current_vector)
        )

        return Response({
            "user_message": message,
            "ai_reply": reply,
            "cached": False,
            "source": "gpt"
        })

    except Exception as e:
        return Response({"error": str(e)}, status=500)