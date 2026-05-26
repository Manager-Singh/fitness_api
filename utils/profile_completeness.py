"""Login / auth responses: detect whether onboarding profile fields are filled."""

from __future__ import annotations

from typing import List, Tuple

from utils.age import get_user_age, get_user_age_exact
from utils.paywall_flags import is_teen_age

# Profile basics (step_1) vs parent heights (step_2) vs posture scan/questionnaire (step_3).
STEP_1_FIELDS = frozenset({"gender", "age", "current_height_cm"})
STEP_2_FIELDS = frozenset({"father_height_cm", "mother_height_cm"})


def _nonempty(val) -> bool:
    if val is None:
        return False
    return str(val).strip() != ""


def is_teen_for_profile_requirements(user) -> bool:
    """Teen onboarding (parent heights): sex-specific teen band (female 13–17, male 13–20)."""
    exact = get_user_age_exact(user)
    if exact is not None:
        return is_teen_age(exact, user=user)
    age_reg = get_user_age(user, default="register")
    if age_reg is not None:
        return is_teen_age(age_years=age_reg, user=user)
    return getattr(user, "account_tier", None) == "teen"


def compute_profile_update_status(user, profile) -> Tuple[bool, List[str]]:
    """
    Returns (is_profile_updated, profile_update_missing).

    Required for everyone: gender, age (from profile.age or birth_date), and height
    (``current_height_cm`` or ``base_height_cm``).

    For teens: also ``father_height_cm`` and ``mother_height_cm``.
    """
    missing: List[str] = []

    if not _nonempty(getattr(profile, "gender", None)):
        missing.append("gender")

    if get_user_age(user, default="register") is None:
        missing.append("age")

    has_height = _nonempty(getattr(profile, "current_height_cm", None)) or _nonempty(
        getattr(profile, "base_height_cm", None)
    )
    if not has_height:
        missing.append("current_height_cm")

    if is_teen_for_profile_requirements(user):
        if not _nonempty(getattr(profile, "father_height_cm", None)):
            missing.append("father_height_cm")
        if not _nonempty(getattr(profile, "mother_height_cm", None)):
            missing.append("mother_height_cm")

    return (len(missing) == 0, missing)


def _posture_onboarding_done(profile, state) -> bool:
    """
    Dashboard posture gate: camera scan **or** manual questionnaire (or state scan flags).
    """
    if getattr(profile, "last_scan", None):
        return True
    if state is None:
        return False
    if bool(getattr(state, "questionnaire_completed", False)):
        return True
    if bool(getattr(state, "scan_completed", False)):
        return True
    if getattr(state, "last_scan_at", None):
        return True
    return False


def compute_step_to_show(user, profile) -> str:
    """
    Single onboarding pointer for the client.

    - ``step_1``: missing gender, age, and/or current height (``current_height_cm`` / ``base_height_cm``).
    - ``step_2``: teen with missing father and/or mother height (only after step_1 is satisfied).
    - ``step_3``: no last scan and no completed manual questionnaire (posture path not done).
    - ``dashboard``: all gates passed.
    """
    from users.models import PostureState

    _, missing = compute_profile_update_status(user, profile)
    mset = set(missing)

    if mset & STEP_1_FIELDS:
        return "step_1"

    if is_teen_for_profile_requirements(user) and (mset & STEP_2_FIELDS):
        return "step_2"

    state = PostureState.objects.filter(user=user).first()
    if not _posture_onboarding_done(profile, state):
        return "step_3"

    return "dashboard"
