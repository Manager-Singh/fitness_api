"""
QA paywall bypass flags — when enabled, users behave as fully paid for their tier.

Settings (apibackend/settings.py):
  ADULT_PAYWALL_DISABLED = True  # adults 21+
  TEEN_PAYWALL_DISABLED = True   # teens 13–20
"""

from __future__ import annotations

from django.conf import settings

from utils.age import get_user_age, get_user_age_exact


def adult_paywall_disabled() -> bool:
    return bool(getattr(settings, "ADULT_PAYWALL_DISABLED", False))


def teen_paywall_disabled() -> bool:
    return bool(getattr(settings, "TEEN_PAYWALL_DISABLED", False))


def is_teen_age(age_exact=None, age_years=None) -> bool:
    try:
        ae = float(age_exact) if age_exact is not None else float(age_years or 0)
    except (TypeError, ValueError):
        ae = float(int(age_years or 0))
    return 13.0 <= ae <= 20.999


def is_adult_age(age_exact=None, age_years=None) -> bool:
    try:
        ae = float(age_exact) if age_exact is not None else float(age_years or 0)
    except (TypeError, ValueError):
        ae = float(int(age_years or 0))
    return ae >= 21.0


def qa_paid_bypass_for_user(user, *, age_exact=None) -> bool:
    """True when this user's tier has paywall disabled for QA."""
    ae = age_exact
    if ae is None:
        ae = get_user_age_exact(user)
    if is_teen_age(ae) and teen_paywall_disabled():
        return True
    if is_adult_age(ae) and adult_paywall_disabled():
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

    if teen_paywall_disabled() and is_teen_age(age_exact):
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

    if adult_paywall_disabled():
        try:
            age = int(get_user_age(user) or 0)
        except Exception:
            age = 0
        if age >= 21:
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
    is_teen = 13.0 <= ae_f <= 20.999
    is_adult = ae_f >= 21.0

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
    if is_teen_age(age_exact) and trial_day is not None and trial_day > 7:
        return True
    return bool(sub.get("full_access_trial_expired", False))
