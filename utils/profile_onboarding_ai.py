"""Build onboarding pain/goal context from UserProfile for AI analysis."""
from __future__ import annotations

import json
from typing import Any

from utils.chatgpt_service import generate_chatgpt_response
from utils.ai_analysis import save_ai_text_analysis

ONBOARDING_BLOCKS = (
    ("onboarding_pain_1", "Pain 1 — height vs peers"),
    ("onboarding_pain_2", "Pain 2 — desire to be taller"),
    ("onboarding_pain_3", "Pain 3 — screen/desk time"),
    ("onboarding_goal", "Goal — emotional response to target height"),
)


def _parse_options(raw) -> list | str | None:
    if raw in (None, ""):
        return None
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("["):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        return raw
    return raw


def extract_onboarding_qa(profile_dict: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return structured Q/A rows from profile dict (model_to_dict or request payload)."""
    if not profile_dict:
        return []
    rows = []
    for prefix, label in ONBOARDING_BLOCKS:
        question = profile_dict.get(f"{prefix}_question")
        answer = profile_dict.get(f"{prefix}_answer")
        options = _parse_options(profile_dict.get(f"{prefix}_options"))
        if not any(v not in (None, "") for v in (question, answer, options)):
            continue
        rows.append(
            {
                "id": prefix,
                "label": label,
                "question": question or "",
                "options": options,
                "answer": answer or "",
            }
        )
    return rows


def has_onboarding_answers(profile_dict: dict[str, Any] | None) -> bool:
    if not profile_dict:
        return False
    return any(
        str(profile_dict.get(f"{prefix}_answer") or "").strip()
        for prefix, _ in ONBOARDING_BLOCKS
    )


def build_onboarding_prompt_section(profile_dict: dict[str, Any] | None) -> str:
    """Markdown-style block for posture / chat AI prompts."""
    qa = extract_onboarding_qa(profile_dict)
    if not qa:
        return ""
    return (
        "\n            ONBOARDING MOTIVATION Q&A (teen onboarding — personalize summary & recommendations):\n\n"
        f"            {json.dumps(qa, indent=2, ensure_ascii=False)}\n"
    )


def _build_onboarding_analysis_prompt(profile_dict: dict[str, Any]) -> str:
    qa = extract_onboarding_qa(profile_dict)
    return f"""
You are a teen height-coaching psychologist and certified posture specialist.

Analyze this user's onboarding answers together with their physical profile.
Focus on motivation, emotional drivers, barriers (peer comparison, desk time), and how the goal answer
should shape coaching tone and priorities.

ONBOARDING Q&A:
{json.dumps(qa, indent=2, ensure_ascii=False)}

PROFILE SNAPSHOT:
- Age: {profile_dict.get("age")}
- Gender: {profile_dict.get("gender")}
- Current height (cm): {profile_dict.get("current_height_cm")}
- Ideal height (cm): {profile_dict.get("ideal_height_cm")}
- Activity: {profile_dict.get("activity_level_answer")}
- Main goal (legacy): {profile_dict.get("main_goal_with_heightmax_answer")}

OUTPUT JSON ONLY:
{{
  "summary": "2-4 sentences tying onboarding answers to a supportive coaching narrative",
  "onboarding_insights": {{
    "primary_pain": "...",
    "motivation_level": "high|medium|low",
    "barrier_focus": "posture|habits|confidence|growth",
    "coaching_tone": "..."
  }},
  "recommendations": [
    {{"title": "...", "description": "1-2 sentences linked to a specific onboarding answer"}}
  ],
  "max_height_gain_inches": 0.0,
  "note": "Short reminder about consistency and realistic expectations"
}}

Provide exactly 5 recommendations. max_height_gain_inches between 0 and 1.5.
"""


def run_onboarding_profile_analysis(user, profile_dict: dict[str, Any]) -> dict[str, Any] | None:
    """
    Call OpenAI using onboarding pain/goal fields; persist text via save_ai_text_analysis.
    Returns parsed GPT dict, error dict, or None if no onboarding answers.
    """
    if not has_onboarding_answers(profile_dict):
        return None

    prompt = _build_onboarding_analysis_prompt(profile_dict)
    gpt_response = None
    for _ in range(3):
        gpt_response = generate_chatgpt_response(
            prompt,
            system_role=(
                "You are a health, posture, and teen motivation coach. "
                "Respond with valid JSON only."
            ),
        )
        if (
            isinstance(gpt_response, dict)
            and not gpt_response.get("error")
            and gpt_response.get("summary")
        ):
            break

    if not gpt_response or gpt_response.get("error"):
        return gpt_response

    save_ai_text_analysis(user, gpt_response)
    return gpt_response


def onboarding_context_line(profile) -> str:
    """One-line context for chatbot (UserProfile instance)."""
    d = {
        f"{prefix}_answer": getattr(profile, f"{prefix}_answer", None)
        for prefix, _ in ONBOARDING_BLOCKS
    }
    parts = []
    for prefix, label in ONBOARDING_BLOCKS:
        ans = d.get(f"{prefix}_answer")
        if ans:
            parts.append(f"{label}: {ans}")
    return "; ".join(parts) if parts else ""
