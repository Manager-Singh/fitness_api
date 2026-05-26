from utils.paywall_flags import (
    adult_paywall_disabled,
    apply_monetization_qa_overlay,
    is_adult_age,
    is_teen_age,
    teen_paywall_disabled,
)


def compute_monetization_flags(age_years, subscription_data, age_exact=None, user=None):
    is_paid = bool(subscription_data.get("is_paid", False))
    is_trial = bool(subscription_data.get("is_trial", False))
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
    }
    if user is not None:
        return apply_monetization_qa_overlay(user, result, age_exact=ae)
    if adult_paywall_disabled() and is_adult:
        result["is_paid"] = True
        result["conversion_enabled"] = True
        result["full_access_trial_expired"] = False
    return result
