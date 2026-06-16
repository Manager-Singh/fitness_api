from utils.paywall_flags import (
    adult_paywall_disabled,
    apply_monetization_qa_overlay,
    effective_is_paid,
    is_adult_age,
    is_teen_age,
    teen_paywall_disabled,
)


from utils.trial_settings import teen_trial_globally_enabled


def compute_monetization_flags(age_years, subscription_data, age_exact=None, user=None):
    is_paid = bool(subscription_data.get("is_paid", False))
    is_trial = bool(subscription_data.get("is_trial", False))
    if not teen_trial_globally_enabled():
        is_trial = False
    trial_day = subscription_data.get("trial_day")
    try:
        trial_day = int(trial_day) if trial_day is not None else None
    except (TypeError, ValueError):
        trial_day = None

    try:
        ae = float(age_exact) if age_exact is not None else float(age_years or 0)
    except (TypeError, ValueError):
        ae = float(int(age_years or 0))

    is_teen = is_teen_age(ae, user=user)
    is_adult = is_adult_age(ae, user=user)

    if teen_paywall_disabled() and is_teen:
        result = {
            "is_paid": True,
            "is_trial": False,
            "trial_day": trial_day if trial_day is not None else 1,
            "is_teen": True,
            "is_adult": False,
            "teen_full_access": True,
            "conversion_enabled": True,
            "full_access_trial_expired": False,
            "teen_trial_enabled": teen_trial_globally_enabled(),
        }
        return apply_monetization_qa_overlay(user, result, age_exact=ae) if user else result

    if adult_paywall_disabled() and is_adult:
        is_paid = True

    teen_full_access = bool(is_paid or (is_trial and (trial_day is None or trial_day <= 7)))
    conversion_enabled = bool(is_paid or (is_teen and teen_full_access))
    full_access_trial_expired = bool(
        is_teen and (not is_paid) and trial_day is not None and trial_day > 7
    )

    result = {
        "is_paid": is_paid,
        "is_trial": is_trial,
        "trial_day": trial_day,
        "is_teen": is_teen,
        "is_adult": is_adult,
        "teen_full_access": teen_full_access,
        "conversion_enabled": conversion_enabled,
        "full_access_trial_expired": full_access_trial_expired,
        "teen_trial_enabled": teen_trial_globally_enabled(),
    }
    if user is not None:
        return apply_monetization_qa_overlay(user, result, age_exact=ae)
    if adult_paywall_disabled() and is_adult:
        result["is_paid"] = True
        result["conversion_enabled"] = True
        result["full_access_trial_expired"] = False
    return result


def is_logging_locked(user) -> bool:
    """
    Monday A2 — strict paywall: unpaid teen and adult accounts cannot log via API.
    QA bypass flags (TEEN_PAYWALL_DISABLED / ADULT_PAYWALL_DISABLED) unlock logging.
    """
    from utils.age import get_user_age_exact
    from utils.check_payment import check_subscription_or_response

    try:
        ae = float(get_user_age_exact(user) or 0)
    except Exception:
        ae = 0.0
    in_band = is_teen_age(ae, user=user) or is_adult_age(ae, user=user)
    if not in_band:
        tier = getattr(user, "account_tier", None)
        in_band = tier in ("teen", "adult")
    if not in_band:
        return False
    sub = check_subscription_or_response(user).data
    return not effective_is_paid(user, sub, age_exact=ae)


def logging_locked_payload(user, *, detail: str | None = None) -> dict | None:
    """Return a 403 body dict when logging is locked, else None."""
    if not is_logging_locked(user):
        return None
    return {
        "detail": detail or "Logging is locked. Subscribe to unlock full access.",
        "paywall_required": True,
        "gate": "subscription_required",
    }
