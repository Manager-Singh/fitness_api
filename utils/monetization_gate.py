def compute_monetization_flags(age_years, subscription_data, age_exact=None):
    is_paid = bool(subscription_data.get("is_paid", False))
    is_trial = bool(subscription_data.get("is_trial", False))
    trial_day = subscription_data.get("trial_day")
    try:
        trial_day = int(trial_day) if trial_day is not None else None
    except (TypeError, ValueError):
        trial_day = None

    # Prefer decimal DOB age when provided (Section 2 / dashboard / trial boundaries).
    try:
        ae = float(age_exact) if age_exact is not None else float(age_years or 0)
    except (TypeError, ValueError):
        ae = float(int(age_years or 0))
    is_teen = 13.0 <= ae <= 20.999
    is_adult = ae >= 21.0
    teen_full_access = bool(is_paid or (is_trial and (trial_day is None or trial_day <= 7)))
    # Section 7: adult free is diagnosis-only; conversion/tracking requires paid.
    conversion_enabled = bool(is_paid or (is_teen and teen_full_access))
    full_access_trial_expired = bool(is_teen and (not is_paid) and trial_day is not None and trial_day > 7)

    return {
        "is_paid": is_paid,
        "is_trial": is_trial,
        "trial_day": trial_day,
        "is_teen": is_teen,
        "is_adult": is_adult,
        "teen_full_access": teen_full_access,
        "conversion_enabled": conversion_enabled,
        "full_access_trial_expired": full_access_trial_expired,
    }
