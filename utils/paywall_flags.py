"""
QA paywall bypass flags — when enabled, users behave as fully paid for their tier.

Settings (apibackend/settings.py):
  ADULT_PAYWALL_DISABLED = True  # adults 21+ (male) / 18+ (female)
  TEEN_PAYWALL_DISABLED = True   # teens 13–20 (male) / 13–17 (female)
"""

from __future__ import annotations

from django.conf import settings

from utils.age import get_user_age, get_user_age_exact
from utils.posture.height_constants import (
    ADULT_ACCOUNT_MIN_AGE_FEMALE,
    ADULT_ACCOUNT_MIN_AGE_MALE,
    TEEN_ACCOUNT_MAX_AGE_FEMALE,
    TEEN_ACCOUNT_MAX_AGE_MALE,
    TEEN_MIN_AGE,
    normalize_sex,
)


def _age_value(age_exact=None, age_years=None) -> float:
    try:
        if age_exact is not None:
            return float(age_exact)
        return float(age_years or 0)
    except (TypeError, ValueError):
        return float(int(age_years or 0))


def user_profile_sex(user) -> str | None:
    """Profile gender when available (``male`` / ``female``)."""
    if user is None:
        return None
    try:
        profile = getattr(user, "profile", None)
        if profile is not None:
            return normalize_sex(getattr(profile, "gender", None))
    except Exception:
        pass
    try:
        from user_profile.models import UserProfile

        profile = UserProfile.objects.filter(user=user).only("gender").first()
        if profile:
            return normalize_sex(profile.gender)
    except Exception:
        pass
    return None


def _resolve_sex(*, gender=None, sex=None, user=None) -> str:
    """Default ``male`` when unknown (matches genetic-height helpers)."""
    return (
        normalize_sex(gender)
        or normalize_sex(sex)
        or user_profile_sex(user)
        or "male"
    )


def account_age_bounds(*, gender=None, sex=None, user=None) -> dict:
    """
    Dashboard / account tier age cutoffs by sex.

    Female: teen 13–17, adult 18+ (biological growth largely complete).
    Male: teen 13–20, adult 21+ (spec teen dashboard band).
    """
    s = _resolve_sex(gender=gender, sex=sex, user=user)
    if s == "female":
        return {
            "teen_min": float(TEEN_MIN_AGE),
            "teen_max": float(TEEN_ACCOUNT_MAX_AGE_FEMALE),
            "adult_min": float(ADULT_ACCOUNT_MIN_AGE_FEMALE),
        }
    return {
        "teen_min": float(TEEN_MIN_AGE),
        "teen_max": float(TEEN_ACCOUNT_MAX_AGE_MALE),
        "adult_min": float(ADULT_ACCOUNT_MIN_AGE_MALE),
    }


def adult_paywall_disabled() -> bool:
    return bool(getattr(settings, "ADULT_PAYWALL_DISABLED", False))


def teen_paywall_disabled() -> bool:
    return bool(getattr(settings, "TEEN_PAYWALL_DISABLED", False))


def is_teen_age(age_exact=None, age_years=None, *, gender=None, sex=None, user=None) -> bool:
    ae = _age_value(age_exact, age_years)
    bounds = account_age_bounds(gender=gender, sex=sex, user=user)
    return bounds["teen_min"] <= ae <= bounds["teen_max"] + 0.999


def is_adult_age(age_exact=None, age_years=None, *, gender=None, sex=None, user=None) -> bool:
    ae = _age_value(age_exact, age_years)
    bounds = account_age_bounds(gender=gender, sex=sex, user=user)
    return ae >= bounds["adult_min"]


def is_teen_routine_age(age_exact=None, age_years=None) -> bool:
    """Teen exercise / Engine 2 band per spec: 13–20 (both sexes)."""
    from utils.posture.height_constants import TEEN_MAX_AGE

    ae = _age_value(age_exact, age_years)
    return float(TEEN_MIN_AGE) <= ae <= float(TEEN_MAX_AGE) + 0.999


def qa_paid_bypass_for_user(user, *, age_exact=None) -> bool:
    """True when this user's tier has paywall disabled for QA."""
    ae = age_exact
    if ae is None:
        ae = get_user_age_exact(user)
    if is_teen_age(ae, user=user) and teen_paywall_disabled():
        return True
    if is_adult_age(ae, user=user) and adult_paywall_disabled():
        return True
    return False


def apply_subscription_qa_overlay(user, payload: dict) -> dict:
    """
    Force subscription payloads to look fully paid (for clients + downstream gates).
    """
    if "is_paid" not in payload:
        return payload

    age_exact = payload.get("age_exact")
    if age_exact is None:
        age_exact = get_user_age_exact(user)

    out = dict(payload)

    if teen_paywall_disabled() and is_teen_age(age_exact, user=user):
        out.update(
            {
                "is_paid": True,
                "is_trial": False,
                "expired": False,
                "plan": out.get("plan") or "QA Full Access",
                "plan_type": "Paid",
                "message": "QA testing: teen paywall disabled (full paid access).",
            }
        )
        if out.get("trial_day") is not None:
            try:
                out["trial_day"] = min(int(out["trial_day"]), 7)
            except (TypeError, ValueError):
                out["trial_day"] = 7

    if adult_paywall_disabled() and is_adult_age(age_exact, user=user):
        out.update(
            {
                "is_paid": True,
                "is_trial": False,
                "expired": False,
                "plan": out.get("plan") or "QA Full Access",
                "plan_type": "Paid",
                "message": "QA testing: adult paywall disabled (full paid access).",
            }
        )

    return out


def apply_monetization_qa_overlay(user, flags: dict, *, age_exact=None) -> dict:
    """Full paid monetization shape for dashboard / spec runtime consumers."""
    ae = age_exact
    if ae is None:
        ae = get_user_age_exact(user)
    try:
        ae_f = float(ae) if ae is not None else 0.0
    except (TypeError, ValueError):
        ae_f = 0.0

    out = dict(flags)
    is_teen = is_teen_age(ae_f, user=user)
    is_adult = is_adult_age(ae_f, user=user)

    if teen_paywall_disabled() and is_teen:
        return {
            **out,
            "is_paid": True,
            "is_trial": False,
            "is_teen": True,
            "is_adult": False,
            "teen_full_access": True,
            "conversion_enabled": True,
            "full_access_trial_expired": False,
        }

    if adult_paywall_disabled() and is_adult:
        return {
            **out,
            "is_paid": True,
            "is_trial": False,
            "is_teen": False,
            "is_adult": True,
            "teen_full_access": bool(out.get("teen_full_access", False)),
            "conversion_enabled": True,
            "full_access_trial_expired": False,
        }

    return out


def effective_is_paid(user, subscription_data: dict | None = None, *, age_exact=None) -> bool:
    if qa_paid_bypass_for_user(user, age_exact=age_exact):
        return True
    return bool((subscription_data or {}).get("is_paid", False))


def effective_full_access_trial_expired(
    user, subscription_data: dict | None = None, *, age_exact=None
) -> bool:
    if qa_paid_bypass_for_user(user, age_exact=age_exact):
        return False
    sub = subscription_data or {}
    if bool(sub.get("is_paid", False)):
        return False
    trial_day = sub.get("trial_day")
    try:
        trial_day = int(trial_day) if trial_day is not None else None
    except (TypeError, ValueError):
        trial_day = None
    if is_teen_age(age_exact, user=user) and trial_day is not None and trial_day > 7:
        return True
    return bool(sub.get("full_access_trial_expired", False))
