from posture_analysis.models import UserPosturalOptimizationData, PosturalRecommendation

def save_ai_analysis(user, ai_analysis: dict):
    summary = ai_analysis.get("summary", "")
    max_gain = ai_analysis.get("max_height_gain_inches", 0.0)
    note = ai_analysis.get("note", "")

    # Extract nested postural scores
    posture = ai_analysis.get("postural_optimization", {})
    spinal = posture.get("spinal_compression", 0)
    collapse = posture.get("posture_collapse", 0)
    pelvic = posture.get("pelvic_tilt_back", 0)
    leg = posture.get("leg_hamstring", 0)

    # Save or update
    user_data, _ = UserPosturalOptimizationData.objects.update_or_create(
        user=user,
        defaults={
            "summary": summary,
            "max_height_gain_inches": max_gain,
            "note": note,
            "spinal_compression": spinal,
            "posture_collapse": collapse,
            "pelvic_tilt_back": pelvic,
            "leg_hamstring": leg,
        }
    )

    # Save recommendations
    user_data.recommendations.all().delete()
    for rec in ai_analysis.get("recommendations", []):
        PosturalRecommendation.objects.create(
            user_data=user_data,
            title=rec.get("title", ""),
            description=rec.get("description", "")
        )

    return user_data


def save_ai_text_analysis(user, ai_analysis: dict):
    """
    Spec-aligned: store GPT-generated *text* only.
    Numeric posture scoring / height math must come from scan or deterministic questionnaire logic,
    not from an LLM.
    """
    summary = ai_analysis.get("summary", "") or ""
    max_gain = ai_analysis.get("max_height_gain_inches", 0.0) or 0.0
    note = ai_analysis.get("note", "") or ""

    # IMPORTANT:
    # `UserPosturalOptimizationData` has non-null numeric fields in DB.
    # When this row does not exist yet, we must create it with safe defaults
    # while still respecting the rule that LLMs must not drive numeric posture math.
    user_data, created = UserPosturalOptimizationData.objects.get_or_create(
        user=user,
        defaults={
            "summary": summary,
            "max_height_gain_inches": max_gain,
            "note": note,
            "spinal_compression": 0,
            "posture_collapse": 0,
            "pelvic_tilt_back": 0,
            "leg_hamstring": 0,
        },
    )
    if not created:
        # Update text fields only; do not overwrite numeric segment fields.
        user_data.summary = summary
        user_data.max_height_gain_inches = max_gain
        user_data.note = note
        user_data.save(update_fields=["summary", "max_height_gain_inches", "note", "updated_at"])

    # Replace recommendations list.
    user_data.recommendations.all().delete()
    for rec in ai_analysis.get("recommendations", []) or []:
        PosturalRecommendation.objects.create(
            user_data=user_data,
            title=rec.get("title", "") or "",
            description=rec.get("description", "") or "",
        )

    return user_data

def save_ai_analysis_full_scan(user, final_response: dict):
    """
    Saves posture analysis safely from final_response
    WITHOUT changing API structure
    """

    analysis = final_response.get("analysis", {})
    summary_block = analysis.get("summary", {})

    summary = summary_block.get("summary", "")
    max_gain = summary_block.get("max_height_gain_inches", 0.0)
    note = summary_block.get("note", "")

    spinal = summary_block.get("spinal_compression", 0)
    collapse = summary_block.get("posture_collapse", 0)
    pelvic = summary_block.get("pelvic_tilt_back", 0)
    leg = summary_block.get("leg_hamstring", 0)

    # -----------------------------
    # Save / Update main record
    # -----------------------------
    user_data, _ = UserPosturalOptimizationData.objects.update_or_create(
        user=user,
        defaults={
            "summary": summary,
            "max_height_gain_inches": max_gain,
            "note": note,
            "spinal_compression": spinal,
            "posture_collapse": collapse,
            "pelvic_tilt_back": pelvic,
            "leg_hamstring": leg,
        }
    )

    # -----------------------------
    # Save recommendations
    # -----------------------------
    user_data.recommendations.all().delete()

    for rec in summary_block.get("recommendations", []):
        PosturalRecommendation.objects.create(
            user_data=user_data,
            title=rec.get("title", ""),
            description=rec.get("description", "")
        )

    return user_data